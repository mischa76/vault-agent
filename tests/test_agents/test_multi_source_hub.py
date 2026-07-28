"""Keyless tests for the WP10 multi-source hub (business-key harmonisation across sources)."""
from vault_agent.agents.code_generator import CodeGeneratorAgent, _render_hub
from vault_agent.agents.staging_generator import build_staging
from vault_agent.rules.dv2_rules import canonical_hub_key_column
from vault_agent.state import DVModel, Hub, HubSource, Satellite, VaultAgentState


def _multi_source_model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(
                name="hub_customer",
                business_key="customer id",
                source_entity="customer",
                description="d",
                sources=[
                    HubSource(source_table="crm_customer", business_key_column="cust_id"),
                    HubSource(source_table="victor_partner", business_key_column="partn_id"),
                ],
            )
        ],
        satellites=[
            Satellite(
                name="sat_customer_details",
                parent="hub_customer",
                attributes=["customer name"],
                description="d",
            )
        ],
    )


# ── canonical key policy (WP10 §2.2) ──────────────────────────────────────────────────────
def test_canonical_key_business_term_when_sources_disagree() -> None:
    hub = _multi_source_model().hubs[0]  # cust_id vs partn_id -> business term
    assert canonical_hub_key_column(hub) == "CUSTOMER_ID"


def test_canonical_key_keeps_source_name_when_sources_agree() -> None:
    hub = Hub(
        name="hub_customer", business_key="customer id", source_entity="customer", description="d",
        sources=[
            HubSource(source_table="crm_customer", business_key_column="CUSTOMER_KEY"),
            HubSource(source_table="victor_partner", business_key_column="customer_key"),
        ],
    )
    assert canonical_hub_key_column(hub) == "CUSTOMER_KEY"  # they agree (normalised)


def test_canonical_key_single_source_is_business_key_normalised() -> None:
    hub = Hub(name="hub_customer", business_key="national customer ID",
              source_entity="customer", description="d")  # no sources
    assert canonical_hub_key_column(hub) == "NATIONAL_CUSTOMER_ID"


# ── the integration property: identical hash input across feeds (WP10 §4.1) ────────────────
def test_two_stages_hash_the_same_canonical_column() -> None:
    result = build_staging(_multi_source_model(), source_schemas=[])
    a = result.metadata["stg_customer_crm_customer"]
    b = result.metadata["stg_customer_victor_partner"]
    # Both stages hash CUSTOMER_HK from the SAME canonical column -> same key value, same HK.
    assert a["hashed_columns"]["CUSTOMER_HK"] == "CUSTOMER_ID"
    assert b["hashed_columns"]["CUSTOMER_HK"] == "CUSTOMER_ID"
    # Each aliases its own physical key column to the canonical name.
    assert a["derived_columns"] == {"CUSTOMER_ID": "CUST_ID"}
    assert b["derived_columns"] == {"CUSTOMER_ID": "PARTN_ID"}
    # Bound verbatim to each source table (no inference flag).
    assert a["source_model"] == "crm_customer" and b["source_model"] == "victor_partner"


async def test_render_hub_unions_source_models_and_keys_off_canonical() -> None:
    sql, meta = _render_hub(_multi_source_model().hubs[0])
    assert meta["source_model"] == ["stg_customer_crm_customer", "stg_customer_victor_partner"]
    assert meta["src_nk"] == "CUSTOMER_ID"
    assert meta["src_pk"] == "CUSTOMER_HK"
    # The rendered SQL uses the list form (AutomateDV hub macro unions a source_model list).
    assert '["stg_customer_crm_customer", "stg_customer_victor_partner"]' in sql
    assert '{%- set src_nk = "CUSTOMER_ID" -%}' in sql


async def test_satellite_splits_per_source_reading_own_staging() -> None:
    state = VaultAgentState(dv_model=_multi_source_model())
    out = await CodeGeneratorAgent().run(state)
    models = out.artifacts.dbt_models
    # One satellite per source, each named + bound to its source's staging.
    assert "sat_customer_details_crm_customer" in models
    assert "sat_customer_details_victor_partner" in models
    assert "sat_customer_details" not in models  # the shared name is not emitted
    assert '"stg_customer_crm_customer"' in models["sat_customer_details_crm_customer"]
    assert '"stg_customer_victor_partner"' in models["sat_customer_details_victor_partner"]
    # Both per-source sats key off the same hub hash key and hashdiff column.
    assert '"CUSTOMER_HK"' in models["sat_customer_details_crm_customer"]
    assert "CUSTOMER_DETAILS_HASHDIFF" in models["sat_customer_details_crm_customer"]


# ── byte-identity guard: an empty-sources hub renders exactly as before ────────────────────
def test_single_source_hub_unchanged_bare_string_source_model() -> None:
    hub = Hub(name="hub_customer", business_key="national customer ID",
              source_entity="customer", description="d")  # sources=[]
    sql, meta = _render_hub(hub)
    assert meta["source_model"] == "stg_customer"  # bare string, not a list
    assert '{%- set source_model = "stg_customer" -%}' in sql
    assert '{%- set src_nk = "NATIONAL_CUSTOMER_ID" -%}' in sql


# ── validator: duplicate feed + per-source grounding ──────────────────────────────────────
def _validate(model: DVModel, schemas: list | None = None) -> list:
    import asyncio

    from vault_agent.agents.validator import ValidatorAgent
    state = VaultAgentState(dv_model=model, source_schemas=schemas or [])
    out = asyncio.run(ValidatorAgent().run(state))
    return out.validation_report.issues


def test_duplicate_feed_is_an_error() -> None:
    model = DVModel(hubs=[Hub(
        name="hub_customer", business_key="customer id", source_entity="customer", description="d",
        sources=[
            HubSource(source_table="crm_customer", business_key_column="cust_id"),
            HubSource(source_table="CRM_CUSTOMER", business_key_column="CUST_ID"),  # same feed
        ],
    )])
    codes = {i.code for i in _validate(model) if i.severity == "error"}
    assert "E_HUB_DUP_FEED" in codes


def test_multi_source_feed_grounding_warning() -> None:
    from vault_agent.state import SourceColumn, SourceTable
    model = DVModel(hubs=[Hub(
        name="hub_customer", business_key="customer id", source_entity="customer", description="d",
        sources=[
            HubSource(source_table="crm_customer", business_key_column="cust_id"),
            HubSource(source_table="victor_partner", business_key_column="partn_id"),
        ],
    )])
    schema = [SourceTable(table="crm_customer", columns=[SourceColumn(name="cust_id")])]
    codes = {i.code for i in _validate(model, schema)}
    # partn_id is not in the declared schema -> per-source grounding warning.
    assert "W_HUBSOURCE_BK_NOT_IN_SOURCE" in codes


# ── ratification: sources form resolves a concept into Hub.sources (WP10 §2.4) ─────────────
def test_ratification_sources_round_trip(tmp_path) -> None:
    import yaml as _yaml

    from vault_agent.agents.orchestrator import apply_human_decision
    from vault_agent.cli import _mapping_sources_from_file

    # A human resolves the unresolved "customer id" key by adding a sources: list.
    review = {
        "proposals": [
            {"concept": "customer id", "sources": [
                {"table": "crm_customer", "column": "cust_id"},
                {"table": "victor_partner", "column": "partn_id"},
            ]},
        ],
    }
    path = tmp_path / "mappings.review.yml"
    path.write_text(_yaml.safe_dump(review), encoding="utf-8")
    parsed = _mapping_sources_from_file(path)
    assert parsed == {"customer id": [
        {"table": "crm_customer", "column": "cust_id"},
        {"table": "victor_partner", "column": "partn_id"},
    ]}

    state = VaultAgentState(
        dv_model=DVModel(hubs=[Hub(name="hub_customer", business_key="customer id",
                                   source_entity="customer", description="d")]),
    )
    state.mappings.unresolved = ["customer id"]
    apply_human_decision(state, {"owners": {}, "accept": False, "mapping_sources": parsed})
    hub = state.dv_model.hubs[0]
    assert [s.source_table for s in hub.sources] == ["crm_customer", "victor_partner"]
    assert [s.business_key_column for s in hub.sources] == ["cust_id", "partn_id"]
    assert "customer id" not in state.mappings.unresolved


# ── WP21 §2.5: the per-source path owes the same collision visibility ──────────────────────
async def test_multi_source_satellite_still_warns_about_colliding_labels() -> None:
    """The per-source branch renders the same column set as _render_satellite, so it must
    surface the same COLUMN_COLLISION warning — once per satellite, not once per feed."""
    from vault_agent.state import FlagKind

    model = _multi_source_model()
    # "customer name" and "customer-name" both normalise to CUSTOMER_NAME: one column, two
    # labels, silently overwriting each other in the payload.
    model.satellites[0].attributes = ["customer name", "customer-name"]
    state = VaultAgentState(dv_model=model)

    result = await CodeGeneratorAgent().run(state)

    collisions = [f for f in result.flags if f.kind == FlagKind.COLUMN_COLLISION]
    assert len(collisions) == 1  # the satellite, not each of its two feeds
    assert collisions[0].asset == "sat_customer_details"
    assert "CUSTOMER_NAME" in collisions[0].message
    # generation still proceeds: one satellite per source
    assert "sat_customer_details_crm_customer" in result.artifacts.dbt_models
