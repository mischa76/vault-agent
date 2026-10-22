"""WP86 — zero-key rows in the hubs (spec §3). Committed before the change, failing. The shapes are
WP83's: a customer link with two roles of `hub_business_entity`, the bill-of-materials link on
`hub_product`."""
from __future__ import annotations

from tests.test_wp83_zero_keys import BOM, BUSINESS_ENTITY, CUSTOMER, ORDERS, PRODUCT, _model
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.staging_generator import unresolved_stage_refs
from vault_agent.state import VaultAgentState


async def _state() -> VaultAgentState:
    state = VaultAgentState(source_schemas=[CUSTOMER, BUSINESS_ENTITY, PRODUCT, BOM, ORDERS],
                            dv_model=_model(), target_platform="postgres")
    await CodeGeneratorAgent().run(state)
    rebind_staging(state)
    return state


async def test_a_zero_keyed_hub_gets_typed_zero_rows_and_a_stage() -> None:
    state = await _state()
    models = state.artifacts.staging_models
    sql = models["zero_keys_business_entity"]
    assert "CAST('-1' AS bigint) AS BUSINESSENTITYID" in sql
    assert "CAST('-2' AS bigint) AS BUSINESSENTITYID" in sql
    assert "AS LOAD_DATETIME" in sql and "'SYSTEM'" in sql
    stage = models["stg_business_entity_zero_keys"]
    assert "source_model: 'zero_keys_business_entity'" in stage
    assert "BUSINESSENTITY_HK: 'BUSINESSENTITYID'" in stage
    meta = state.artifacts.automatedv_yaml["staging"]["stg_business_entity_zero_keys"]
    assert meta["source_binding"] == "generated"


async def test_the_hub_reads_the_zero_key_stage() -> None:
    state = await _state()
    hub_sql = state.artifacts.dbt_models["hub_business_entity"]
    assert '"stg_business_entity_zero_keys"' in hub_sql
    meta = state.artifacts.automatedv_yaml["hubs"]["hub_business_entity"]
    assert meta["source_model"][-1] == "stg_business_entity_zero_keys"
    assert "stg_product_zero_keys" in state.artifacts.automatedv_yaml["hubs"]["hub_product"][
        "source_model"]


async def test_a_hub_no_zero_keyed_participation_reaches_is_unchanged() -> None:
    state = await _state()
    # hub_order_day is reached only through a datetime participation (WP83 rule 2)
    assert "zero_keys_order_day" not in state.artifacts.staging_models
    hubs = state.artifacts.automatedv_yaml["hubs"]
    assert hubs["hub_order_day"]["source_model"] == "stg_order_day"


async def test_the_zero_key_stage_resolves_at_parse_time() -> None:
    state = await _state()
    sources_yml = state.artifacts.scaffolding["models/staging/sources.yml"]
    assert "stg_business_entity_zero_keys" not in unresolved_stage_refs(
        state.artifacts.staging_models, sources_yml)
