"""WP85 — a satellite whose key does not cover a unique key of its relation is refused
(`E_SAT_GRAIN_NOT_UNIQUE`, spec §3). Committed before the change, failing. The shape is the owner's
bill of materials: a link on (assembly, component, unit) over a table unique on
(assembly, component, StartDate), its detail satellite sharing the link's stage."""
from __future__ import annotations

from typing import Any

from eval.adventureworks.derive import build_source_schema
from eval.adventureworks.extract import parse
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import DVModel, SourceTable, VaultAgentState

PRODUCT = SourceTable.model_validate({
    "table": "Product", "schema": "Production", "columns": ["ProductID", "Name"],
    "primary_key": ["ProductID"],
})
UNIT = SourceTable.model_validate({
    "table": "UnitMeasure", "schema": "Production", "columns": ["UnitMeasureCode", "Name"],
    "primary_key": ["UnitMeasureCode"],
})
BOM = SourceTable.model_validate({
    "table": "BillOfMaterials", "schema": "Production",
    "columns": ["BillOfMaterialsID", "ProductAssemblyID", "ComponentID", "StartDate",
                "UnitMeasureCode", "PerAssemblyQty"],
    "primary_key": ["BillOfMaterialsID"],
    "unique_keys": [["ProductAssemblyID", "ComponentID", "StartDate"]],
    # The declared foreign keys are what binds the freely named link to this relation (WP42's
    # offer) — at validation time, before the mapper's re-bind.
    "foreign_keys": [
        {"columns": ["ProductAssemblyID"], "references_table": "Product",
         "references_columns": ["ProductID"]},
        {"columns": ["ComponentID"], "references_table": "Product",
         "references_columns": ["ProductID"]},
        {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
         "references_columns": ["UnitMeasureCode"]},
    ],
})


def _model(sat: dict[str, Any]) -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": "ProductID", "source_entity": "Product",
             "description": "p"},
            {"name": "hub_unit_measure", "business_key": "UnitMeasureCode",
             "source_entity": "UnitMeasure", "description": "u"},
        ],
        "links": [{"name": "link_product_assembly_component", "description": "bom",
                   "connected_hubs": [
                       {"hub": "hub_product", "role": "assembly",
                        "source_key_column": "ProductAssemblyID"},
                       {"hub": "hub_product", "role": "component",
                        "source_key_column": "ComponentID"},
                       {"hub": "hub_unit_measure"},
                   ]}],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "source_table": "Product", "description": "d"},
            {"name": "sat_product_assembly_component_details",
             "parent": "link_product_assembly_component", "attributes": ["PerAssemblyQty"],
             "description": "quantities", **sat},
        ],
    })


async def _issues(model: DVModel, tables: list[SourceTable] | None = None,
                  existing: DVModel | None = None) -> list[Any]:
    state = VaultAgentState(source_schemas=tables or [PRODUCT, UNIT, BOM], dv_model=model,
                            existing_model=existing)
    await CodeGeneratorAgent().run(state)
    await ValidatorAgent().run(state)
    return [i for i in state.validation_report.issues if i.code == "E_SAT_GRAIN_NOT_UNIQUE"]


# ── §2 rule 2: the gate ────────────────────────────────────────────────────────────────────
async def test_the_bill_of_materials_detail_satellite_is_refused() -> None:
    issues = await _issues(_model({}))
    assert [i.construct for i in issues] == ["sat_product_assembly_component_details"]
    assert issues[0].severity == "error"
    assert "STARTDATE" in issues[0].message.upper()
    assert issues[0].remedy and "child_dependent_key" in issues[0].remedy
    assert "StartDate" in issues[0].remedy or "STARTDATE" in issues[0].remedy


async def test_its_multi_active_form_on_start_date_passes() -> None:
    issues = await _issues(_model({"sat_type": "multi_active",
                                   "child_dependent_key": ["StartDate"]}))
    assert issues == []


async def test_a_hub_satellite_on_the_primary_key_passes() -> None:
    issues = await _issues(_model({"sat_type": "multi_active",
                                   "child_dependent_key": ["StartDate"]}))
    assert all(i.construct != "sat_product_details" for i in issues)


async def test_a_relation_without_declared_keys_is_not_judged() -> None:
    keyless = SourceTable.model_validate({**BOM.model_dump(by_alias=True),
                                          "primary_key": [], "unique_keys": []})
    assert await _issues(_model({}), [PRODUCT, UNIT, keyless]) == []


async def test_a_pre_existing_satellite_is_not_judged() -> None:
    model = _model({})
    assert await _issues(model, existing=model) == []


# ── §2 rule 1: the catalogue carries keys ──────────────────────────────────────────────────
_DDL = """
CREATE TABLE [Production].[BillOfMaterials](
    [BillOfMaterialsID] [int] IDENTITY (1, 1) NOT NULL,
    [ProductAssemblyID] [int] NULL,
    [ComponentID] [int] NOT NULL,
    [StartDate] [datetime] NOT NULL
) ON [PRIMARY];
GO
ALTER TABLE [Production].[BillOfMaterials] WITH CHECK ADD
    CONSTRAINT [PK_BillOfMaterials_BillOfMaterialsID] PRIMARY KEY NONCLUSTERED
    (
        [BillOfMaterialsID]
    )  ON [PRIMARY];
GO
"""
_DDL += (
    "CREATE UNIQUE CLUSTERED INDEX [AK_BillOfMaterials_ProductAssemblyID_ComponentID_StartDate]"
    " ON [Production].[BillOfMaterials]([ProductAssemblyID], [ComponentID], [StartDate])"
    " ON [PRIMARY];\nGO\n"
)


def test_the_extract_reads_with_check_primary_keys_and_clustered_unique_indexes() -> None:
    (table,) = parse(_DDL)
    assert table.primary_key == ["BillOfMaterialsID"]
    assert [ak["columns"] for ak in table.alternate_keys] == [
        ["ProductAssemblyID", "ComponentID", "StartDate"]
    ]


def test_derive_writes_the_keys() -> None:
    from dataclasses import asdict

    (table,) = parse(_DDL)
    extract = {"tables": [asdict(table)], "user_defined_types": {}}
    (declared,) = build_source_schema(extract, "Production")["source_schemas"]
    assert declared["primary_key"] == ["BillOfMaterialsID"]
    assert declared["unique_keys"] == [["ProductAssemblyID", "ComponentID", "StartDate"]]
    assert SourceTable.model_validate(declared).unique_keys == [
        ["ProductAssemblyID", "ComponentID", "StartDate"]
    ]


def test_a_commented_out_key_column_is_not_a_key_column() -> None:
    """Found by the pre-registration (P2): the install script comments a third column out of
    `PK_SalesPersonQuotaHistory` (`[QuotaDate] --,` / `-- [ProductCategoryID]`), and the parser
    read it as part of the key — a column the table does not have."""
    ddl = (
        "CREATE TABLE [Sales].[SalesPersonQuotaHistory](\n"
        "    [BusinessEntityID] [int] NOT NULL,\n    [QuotaDate] [datetime] NOT NULL\n"
        ") ON [PRIMARY];\nGO\n"
        "ALTER TABLE [Sales].[SalesPersonQuotaHistory] WITH CHECK ADD\n"
        "    CONSTRAINT [PK_SalesPersonQuotaHistory_BusinessEntityID_QuotaDate] PRIMARY KEY "
        "CLUSTERED\n    (\n        [BusinessEntityID],\n        [QuotaDate] --,\n"
        "        -- [ProductCategoryID]\n    )  ON [PRIMARY];\nGO\n"
    )
    (table,) = parse(ddl)
    assert table.primary_key == ["BusinessEntityID", "QuotaDate"]
