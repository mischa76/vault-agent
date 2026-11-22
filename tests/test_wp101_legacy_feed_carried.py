"""WP101 — the grandfathered feed stays grandfathered on every later step, and the satellite it
carried stays with it (C34, C35). Committed before the change, failing. The shape is arm A's fifth
project (the C1 experiment, 2026-10-30): `hub_unit_measure` single-source in step 3 with a
satellite, multi-source from step 4; step 5 renamed the legacy feed's stage while the satellite
still read the old name, and from step 4 on the other feed's stage hashed the satellite's `NAME`,
which it does not have."""
from __future__ import annotations

import pytest

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import (
    build_staging,
    legacy_feeds,
    unresolved_raw_vault_refs,
)
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Satellite,
    SourceTable,
    VaultAgentState,
)

FEEDS = [HubSource(source_table="customer", business_key_column="customer_id"),
         HubSource(source_table="crm_account", business_key_column="cust_no")]
BINDINGS = {"stg_customer": "customer"}
LEGACY = ("hub_customer", normalize_identifier("customer"), normalize_identifier("customer_id"))
CUSTOMER = SourceTable(table="customer", schema="raw", columns=["customer_id", "full_name"])
CRM = SourceTable(table="crm_account", schema="raw", columns=["cust_no", "segment"])


def _vault(*, multi: bool) -> DVModel:
    return DVModel(
        hubs=[Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
                  description="c", sources=list(FEEDS) if multi else [])],
        satellites=[Satellite(name="sat_customer_details", parent="hub_customer",
                              attributes=["full_name"], description="d")],
    )


def _unresolved(state: VaultAgentState) -> list[str]:
    return unresolved_raw_vault_refs(state.artifacts.dbt_models, state.artifacts.staging_models)


def _reads(stage: str) -> str:
    return f'{{%- set source_model = "{stage}" -%}}\n'


def _state(existing: DVModel, merged: DVModel, bindings: dict[str, str] | None) -> VaultAgentState:
    state = VaultAgentState(source_schemas=[CUSTOMER, CRM])
    state.existing_model = existing
    state.dv_model = merged
    state.carried_bindings = dict(bindings or {})
    return state


# ── §2 rule 1: the catalogue says which feed is grandfathered ──────────────────────────────
def test_an_already_multi_source_hubs_legacy_feed_is_read_from_the_carried_binding() -> None:
    assert legacy_feeds(_vault(multi=True), BINDINGS) == {LEGACY}


@pytest.mark.parametrize(
    "bindings", [{}, {"stg_customer": "vendor"}, {"stg_customer_customer": "customer"}]
)
def test_without_the_unsuffixed_binding_nothing_is_grandfathered(bindings: dict[str, str]) -> None:
    assert legacy_feeds(_vault(multi=True), bindings) == set()


def test_a_single_source_existing_hub_is_grandfathered_as_before() -> None:
    assert legacy_feeds(_vault(multi=False), {}) == {LEGACY}


# ── §2 rule 2: the step after next keeps the name and the satellite's binding ──────────────
async def test_the_step_after_next_keeps_the_legacy_stage_and_the_satellite_reads_it() -> None:
    state = _state(_vault(multi=True), _vault(multi=True), BINDINGS)
    await CodeGeneratorAgent().run(state)
    assert "stg_customer" in state.artifacts.staging_models
    assert "stg_customer_customer" not in state.artifacts.staging_models
    assert 'source_model = "stg_customer"' in state.artifacts.dbt_models["sat_customer_details"]
    assert '"stg_customer"' in state.artifacts.dbt_models["hub_customer"]
    assert _unresolved(state) == []


@pytest.mark.parametrize("existing_multi", [False, True])
async def test_the_existing_satellites_payload_stays_with_the_legacy_feed(
    existing_multi: bool,
) -> None:
    state = _state(_vault(multi=existing_multi), _vault(multi=True), BINDINGS)
    await CodeGeneratorAgent().run(state)
    other = state.artifacts.staging_models["stg_customer_crm_account"]
    assert "CUSTOMER_DETAILS_HASHDIFF" not in other and "FULL_NAME" not in other
    legacy = state.artifacts.staging_models["stg_customer"]
    assert "CUSTOMER_DETAILS_HASHDIFF" in legacy and "FULL_NAME" in legacy


# ── §2 rule 3: not identifiable, not guessed ───────────────────────────────────────────────
async def test_without_a_carried_binding_the_existing_satellite_is_flagged_not_guessed() -> None:
    state = _state(_vault(multi=True), _vault(multi=True), None)
    await CodeGeneratorAgent().run(state)
    assert "sat_customer_details" not in state.artifacts.dbt_models
    assert any(f.kind == FlagKind.GENERATION_GAP and f.asset == "sat_customer_details"
               for f in state.flags)
    assert not any(
        "CUSTOMER_DETAILS_HASHDIFF" in sql for sql in state.artifacts.staging_models.values()
    )
    assert _unresolved(state) == []


# ── §2 rule 4: the project's own check sees the raw vault ──────────────────────────────────
def test_unresolved_raw_vault_refs_names_a_model_reading_an_unrendered_stage() -> None:
    models = {
        "sat_x": '{%- set source_model = "stg_x" -%}\n',
        "hub_y": '{%- set source_model = ["stg_y", "stg_y_zero_keys"] -%}\n',
        "link_z": "select * from {{ ref('stg_z') }}\n",
        "sat_ok": '{%- set source_model = "stg_y" -%}\n',
    }
    staging = {"stg_y": "", "stg_y_zero_keys": ""}
    assert unresolved_raw_vault_refs(models, staging) == ["link_z", "sat_x"]


def test_the_scorer_fails_on_a_raw_vault_model_reading_an_unrendered_stage() -> None:
    from eval.scorers import project_self_contained

    case = type("Case", (), {})()
    staging = build_staging(_vault(multi=False), [CUSTOMER])
    state = VaultAgentState(dv_model=_vault(multi=False))
    state.artifacts.staging_models = staging.models
    state.artifacts.scaffolding = staging.scaffolding
    state.artifacts.dbt_models = {"sat_customer_details": _reads("stg_customer")}
    assert project_self_contained(state, case).score == 1.0
    state.artifacts.dbt_models = {"sat_customer_details": _reads("stg_gone")}
    verdict = project_self_contained(state, case)
    assert verdict.score == 0.0 and "sat_customer_details" in verdict.details
