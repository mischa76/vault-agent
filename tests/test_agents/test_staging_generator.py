"""Unit tests for the staging-layer generator (deterministic, no API key).

The fixture mirrors the bank Durchstich (demo/bank_postgres) so the generated staging
models can be asserted against the hand-authored ones the Postgres run verified: same
hash keys, same hashdiffs, same APPLIED_DTS derivation on the eff_sat parent.
"""
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import (
    PROJECT_NAME,
    build_staging,
    collect_staging_specs,
)
from vault_agent.rules.dv2_rules import AUTOMATE_DV_VERSION
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    Satellite,
    SourceTable,
    VaultAgentState,
)


def _bank_model() -> DVModel:
    """The bank Durchstich shape: 2 hubs, 1 link with driving key, 2 sats, 1 eff_sat."""
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="national customer ID",
                source_entity="customer", description="a customer"),
            Hub(name="hub_account", business_key="account number",
                source_entity="account", description="an account"),
        ],
        links=[
            Link(name="link_account_customer",
                 connected_hubs=["hub_account", "hub_customer"],
                 description="ownership", driving_key=["hub_account"]),
        ],
        satellites=[
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["customer name", "date of birth"],
                      description="customer payload"),
            Satellite(name="sat_account_details", parent="hub_account",
                      attributes=["balance", "status"], description="account payload"),
            Satellite(name="sat_account_customer_eff", parent="link_account_customer",
                      attributes=["effective from", "effective to"],
                      description="ownership validity", sat_type="effectivity"),
        ],
    )


def test_collects_one_staging_model_per_source() -> None:
    specs = collect_staging_specs(_bank_model())
    assert set(specs) == {"stg_customer", "stg_account", "stg_account_customer"}


def test_hub_staging_matches_the_verified_demo_shape() -> None:
    specs = collect_staging_specs(_bank_model())
    customer = specs["stg_customer"]

    assert customer.hashed == [
        ("CUSTOMER_HK", "NATIONAL_CUSTOMER_ID"),
        ("CUSTOMER_DETAILS_HASHDIFF", customer.hashed[1][1]),
    ]
    hashdiff = customer.hashed[1][1]
    assert getattr(hashdiff, "columns", None) == ["CUSTOMER_NAME", "DATE_OF_BIRTH"]
    assert customer.source_columns == [
        "NATIONAL_CUSTOMER_ID", "CUSTOMER_NAME", "DATE_OF_BIRTH",
        "LOAD_DATETIME", "RECORD_SOURCE",
    ]


def test_link_staging_hashes_both_hubs_and_the_link() -> None:
    specs = collect_staging_specs(_bank_model())
    link = specs["stg_account_customer"]

    names = [name for name, _ in link.hashed]
    assert names == ["ACCOUNT_HK", "CUSTOMER_HK", "LINK_ACCOUNT_CUSTOMER_HK"]
    # The link HK is a multi-column hash over the BKs in connected_hubs order.
    assert link.hashed[2][1] == ["ACCOUNT_NUMBER", "NATIONAL_CUSTOMER_ID"]


def test_eff_sat_parent_gets_the_applied_dts_derived_column() -> None:
    specs = collect_staging_specs(_bank_model())
    link = specs["stg_account_customer"]

    # src_eff is a DEDICATED derived column carrying the start date (the Postgres
    # "specified more than once" fix — rules.EFFECTIVITY_APPLIED_COLUMN).
    assert link.derived == {"APPLIED_DTS": "EFFECTIVE_FROM"}
    assert "EFFECTIVE_FROM" in link.source_columns
    assert "EFFECTIVE_TO" in link.source_columns


def test_rendered_stage_model_calls_automate_dv_stage() -> None:
    result = build_staging(_bank_model(), source_schemas=[])
    sql = result.models["stg_customer"]

    assert "{{ config(materialized='view') }}" in sql
    assert "automate_dv.stage(include_source_columns=true" in sql
    assert "source_model: 'raw_customer'" in sql
    assert "CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'" in sql
    assert "is_hashdiff: true" in sql
    assert "derived_columns=none," in sql

    link_sql = result.models["stg_account_customer"]
    assert "APPLIED_DTS: 'EFFECTIVE_FROM'" in link_sql
    assert "derived_columns=metadata_dict['derived_columns']," in link_sql


def test_unmatched_binding_is_inferred_and_flagged() -> None:
    result = build_staging(_bank_model(), source_schemas=[])

    assert {f.kind for f in result.flags} == {FlagKind.SOURCE_BINDING}
    assert {f.asset for f in result.flags} == {
        "stg_customer", "stg_account", "stg_account_customer",
    }
    assert all(f.severity == "advisory" for f in result.flags)


def test_declared_source_table_binds_verbatim_without_a_flag() -> None:
    schemas = [
        SourceTable(table="raw_customer", columns=["NATIONAL_CUSTOMER_ID"]),
        SourceTable(table="ACCOUNT", columns=["ACCOUNT_NUMBER"]),  # matches by base name
    ]
    result = build_staging(_bank_model(), source_schemas=schemas)

    assert "source_model: 'raw_customer'" in result.models["stg_customer"]
    assert "source_model: 'ACCOUNT'" in result.models["stg_account"]
    # Only the link staging is unmatched and flagged.
    assert {f.asset for f in result.flags} == {"stg_account_customer"}


def test_scaffolding_makes_a_runnable_project() -> None:
    result = build_staging(_bank_model(), source_schemas=[])

    assert set(result.scaffolding) == {
        "dbt_project.yml", "packages.yml", "models/staging/sources.yml", "README.md",
    }
    project = result.scaffolding["dbt_project.yml"]
    assert f"name: '{PROJECT_NAME}'" in project
    assert "+quote_columns: false" in project
    assert "+materialized: view" in project and "+materialized: incremental" in project
    assert AUTOMATE_DV_VERSION in result.scaffolding["packages.yml"]
    sources = result.scaffolding["models/staging/sources.yml"]
    assert "- name: raw_customer" in sources
    assert "NATIONAL_CUSTOMER_ID" in sources


def test_transactional_link_payload_passes_through_unhashed() -> None:
    model = _bank_model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional",
             payload=["amount", "currency"], event_timestamp="booked at"),
    )
    specs = collect_staging_specs(model)
    txn = specs["stg_transaction"]

    names = [name for name, _ in txn.hashed]
    assert names == ["ACCOUNT_HK", "CUSTOMER_HK", "LINK_TRANSACTION_HK"]
    for col in ("AMOUNT", "CURRENCY", "BOOKED_AT"):
        assert col in txn.source_columns


def test_skipped_constructs_get_no_staging() -> None:
    model = DVModel(
        hubs=[Hub(name="hub_customer", business_key="id", source_entity="customer",
                  description="c")],
        links=[Link(name="link_ghost", connected_hubs=["hub_customer", "hub_missing"],
                    description="dangling")],
        satellites=[Satellite(name="sat_orphan", parent="link_ghost",
                              attributes=["x"], description="orphan")],
    )
    specs = collect_staging_specs(model)
    assert set(specs) == {"stg_customer"}


async def test_agent_wires_staging_into_artifacts_and_metadata() -> None:
    state = VaultAgentState(dv_model=_bank_model())
    result = await CodeGeneratorAgent().run(state)

    assert set(result.artifacts.staging_models) == {
        "stg_customer", "stg_account", "stg_account_customer",
    }
    assert set(result.artifacts.scaffolding) == {
        "dbt_project.yml", "packages.yml", "models/staging/sources.yml", "README.md",
    }
    staging_meta = result.artifacts.automatedv_yaml["staging"]
    assert staging_meta["stg_account_customer"]["derived_columns"] == {
        "APPLIED_DTS": "EFFECTIVE_FROM"
    }
    assert result.decisions[-1]["staging_models"] == 3
    # Ungrounded run: the three inferred bindings are advisory flags, nothing else.
    assert {f.kind for f in result.flags} == {FlagKind.SOURCE_BINDING}
