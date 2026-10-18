"""WP79 — a source column named like a reserved word is escaped and aliased in the stage, per
target platform (spec §3). Committed before the change, failing. The fixture is the twenty-first
chain's `SalesTerritory` shape that failed on PostgreSQL with `syntax error at or near "group"`."""
from __future__ import annotations

import yaml

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import build_staging
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import (
    RESERVED_COLUMN_WORDS,
    is_reserved_column,
    stage_column_name,
)
from vault_agent.rules.platforms import platform_profile
from vault_agent.state import DVModel, SourceTable, VaultAgentState

TERRITORY = SourceTable(
    table="SalesTerritory", schema="Sales",
    columns=["TerritoryID", "Name", "CountryRegionCode", "Group", "SalesYTD", "ModifiedDate"],
)


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [{"name": "hub_sales_territory", "business_key": "TerritoryID",
                  "source_entity": "SalesTerritory", "description": "t"}],
        "links": [],
        "satellites": [{"name": "sat_sales_territory_details", "parent": "hub_sales_territory",
                        "attributes": ["Name", "Group", "SalesYTD"],
                        "source_table": "SalesTerritory", "description": "d"}],
    })


# ── §3.1 / §3.2 the rules ──────────────────────────────────────────────────────────────────
def test_the_reserved_list_and_the_alias() -> None:
    assert len(RESERVED_COLUMN_WORDS) == 101
    assert {"GROUP", "PRIMARY", "ORDER", "USER"} <= RESERVED_COLUMN_WORDS
    for word in ("Group", "group", "PRIMARY", "Order"):
        assert is_reserved_column(word), word
    for word in ("Name", "Size", "ProductID", "Class", "Style"):
        assert not is_reserved_column(word), word
    assert stage_column_name("Group") == "GROUP_"
    assert stage_column_name("ProductID") == "PRODUCTID"


def test_the_physical_spelling_is_the_platforms() -> None:
    assert platform_profile("postgres").physical_name("Group") == "group"
    assert platform_profile("databricks").physical_name("Group") == "Group"


# ── §3.3 the stage ─────────────────────────────────────────────────────────────────────────
def test_the_stage_escapes_and_aliases_the_reserved_column_for_postgres() -> None:
    result = build_staging(_model(), [TERRITORY], target_platform="postgres")
    sql = result.models["stg_sales_territory_details"]
    assert "derived_columns:" in sql
    assert "  GROUP_:\n    source_column: 'group'\n    escape: true" in sql
    yaml_block = sql.split("{%- set yaml_metadata -%}")[1].split("{%- endset -%}")[0]
    meta = yaml.safe_load(yaml_block)
    hashdiff = meta["hashed_columns"]["SALES_TERRITORY_DETAILS_HASHDIFF"]["columns"]
    assert "GROUP_" in hashdiff and "GROUP" not in hashdiff
    assert "NAME" in hashdiff  # not reserved in PostgreSQL: untouched
    stored = result.metadata["stg_sales_territory_details"]
    assert stored["derived_columns"]["GROUP_"] == {"source_column": "group", "escape": True}
    assert "GROUP_" in stored["hashed_columns"]["SALES_TERRITORY_DETAILS_HASHDIFF"]["columns"]


def test_databricks_keeps_the_declared_spelling() -> None:
    result = build_staging(_model(), [TERRITORY], target_platform="databricks")
    sql = result.models["stg_sales_territory_details"]
    assert "  GROUP_:\n    source_column: 'Group'\n    escape: true" in sql


async def test_the_column_gate_accepts_the_alias() -> None:
    state = VaultAgentState(source_schemas=[TERRITORY], dv_model=_model(),
                            target_platform="postgres")
    await CodeGeneratorAgent().run(state)
    await ValidatorAgent().run(state)
    codes = [i.code for i in state.validation_report.issues if i.severity == "error"]
    assert codes == []


# ── §3.4 the raw vault ─────────────────────────────────────────────────────────────────────
async def test_the_satellite_payload_names_the_alias() -> None:
    state = VaultAgentState(source_schemas=[TERRITORY], dv_model=_model(),
                            target_platform="postgres")
    await CodeGeneratorAgent().run(state)
    sat = state.artifacts.dbt_models["sat_sales_territory_details"]
    assert '"GROUP_"' in sat and '"GROUP"' not in sat
    assert "NAME" in sat


async def test_a_hub_keyed_on_a_reserved_word() -> None:
    orders = SourceTable(table="Orders", schema="Sales", columns=["Order", "Total"])
    model = DVModel.model_validate({
        "hubs": [{"name": "hub_order", "business_key": "Order", "source_entity": "Orders",
                  "description": "o"}],
        "links": [], "satellites": [],
    })
    state = VaultAgentState(source_schemas=[orders], dv_model=model, target_platform="postgres")
    await CodeGeneratorAgent().run(state)
    hub = state.artifacts.dbt_models["hub_order"]
    assert '"ORDER_"' in hub and '"ORDER"' not in hub
    stage = state.artifacts.staging_models["stg_order"]
    assert "  ORDER_:\n    source_column: 'order'\n    escape: true" in stage
    assert "ORDERS_HK: 'ORDER_'" in stage
