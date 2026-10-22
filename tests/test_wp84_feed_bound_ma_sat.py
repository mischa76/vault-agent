"""WP84 — a multi-active satellite bound to one feed of a multi-source hub is generated as `ma_sat`
(spec §3). Committed before the change, failing. The shape is the owner's `hub_business_entity`
with its `EmployeePayHistory` feed and the pay-rate history keyed by `RateChangeDate`."""
from __future__ import annotations

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.state import DVModel, FlagKind, SourceTable, VaultAgentState

TABLES = [
    SourceTable(table="BusinessEntity", schema="Person", columns=["BusinessEntityID"]),
    SourceTable(table="EmployeePayHistory", schema="HumanResources",
                columns=["BusinessEntityID", "RateChangeDate", "Rate", "PayFrequency"]),
]


def _model(sat_type: str = "multi_active", cdk: list[str] | None = None) -> DVModel:
    return DVModel.model_validate({
        "hubs": [{"name": "hub_business_entity", "business_key": "BusinessEntityID",
                  "source_entity": "BusinessEntity", "description": "party",
                  "sources": [
                      {"source_table": "BusinessEntity", "business_key_column": "BusinessEntityID"},
                      {"source_table": "EmployeePayHistory",
                       "business_key_column": "BusinessEntityID"},
                  ]}],
        "links": [],
        "satellites": [{
            "name": "sat_business_entity_pay_history", "parent": "hub_business_entity",
            "attributes": ["Rate", "PayFrequency"], "sat_type": sat_type,
            "child_dependent_key": ["RateChangeDate"] if cdk is None else cdk,
            "source_table": "EmployeePayHistory", "description": "pay rates",
        }],
    })


async def _generate(model: DVModel) -> VaultAgentState:
    state = VaultAgentState(source_schemas=TABLES, dv_model=model)
    await CodeGeneratorAgent().run(state)
    return state


async def test_a_feed_bound_multi_active_satellite_is_an_ma_sat() -> None:
    state = await _generate(_model())
    sql = state.artifacts.dbt_models["sat_business_entity_pay_history"]
    assert "automate_dv.ma_sat(" in sql
    assert '{%- set src_cdk = ["RATECHANGEDATE"] -%}' in sql
    assert 'source_model = "stg_business_entity_employeepayhistory"' in sql
    meta = state.artifacts.automatedv_yaml["satellites"]["sat_business_entity_pay_history"]
    assert meta["src_cdk"] == ["RATECHANGEDATE"]
    assert meta["source_model"] == "stg_business_entity_employeepayhistory"


async def test_without_a_child_dependent_key_it_is_flagged_not_generated() -> None:
    state = await _generate(_model(cdk=[]))
    assert "sat_business_entity_pay_history" not in state.artifacts.dbt_models
    assert any(f.kind == FlagKind.GENERATION_GAP and f.asset == "sat_business_entity_pay_history"
               for f in state.flags)


async def test_a_feed_bound_standard_satellite_is_unchanged() -> None:
    state = await _generate(_model(sat_type="standard", cdk=[]))
    sql = state.artifacts.dbt_models["sat_business_entity_pay_history"]
    assert "automate_dv.sat(" in sql and "src_cdk" not in sql
