"""WP133 (C69) — the satellite grain gate (`E_SAT_GRAIN_NOT_UNIQUE`, WP85) also judges a
satellite whose stage reads through a translation view. Written FIRST. WP85's gate skipped every
such stage; since WP125 `hub_product` is keyed on the product number, so the bill of materials —
the very case the gate was built for (C13) — reads through one: its detail satellite, keyed on
(assembly, component, unit) over a table unique on (assembly, component, StartDate), inserted
195 rows again on every build of the demo's replayed project (2026-11-15). A translated key
stands for the relation's referencing column; the stage's metadata says which, typed. Keyless."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import apply_key_licenses
from vault_agent.state import DVModel, KeyLicense, SourceTable, VaultAgentState

CODE = "E_SAT_GRAIN_NOT_UNIQUE"
SAT = "sat_product_assembly_component_details"
STAGE = "stg_product_assembly_component"
PRODUCT = SourceTable(table="Product", schema="Production", primary_key=["ProductID"],
                      columns=["ProductID", "ProductNumber", "Name"])
UNIT = SourceTable(table="UnitMeasure", schema="Production", primary_key=["UnitMeasureCode"],
                   columns=["UnitMeasureCode", "Name"])
KEYS = ("ProductAssemblyID", "ComponentID")


def _bom(unique: list[str]) -> SourceTable:
    return SourceTable.model_validate({
        "table": "BillOfMaterials", "schema": "Production",
        "columns": ["BillOfMaterialsID", *KEYS, "StartDate", "UnitMeasureCode",
                    "PerAssemblyQty"],
        "primary_key": ["BillOfMaterialsID"], "unique_keys": [unique],
        "foreign_keys": [
            *({"columns": [k], "references_table": "Product", "references_columns": ["ProductID"],
               "references_schema": "Production"} for k in KEYS),
            {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
             "references_columns": ["UnitMeasureCode"], "references_schema": "Production"},
        ],
    })


def _delta(sat: dict[str, Any]) -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_unit_measure", "business_key": "UnitMeasureCode",
             "source_entity": "UnitMeasure", "description": "A unit of measure."},
        ],
        "links": [{
            "name": "link_product_assembly_component", "description": "A component.",
            "connected_hubs": [{"hub": "hub_product"}, {"hub": "hub_product", "role": "component"},
                               {"hub": "hub_unit_measure"}],
        }],
        "satellites": [{"name": SAT, "parent": "link_product_assembly_component",
                        "attributes": ["PerAssemblyQty"], "description": "Quantities.", **sat}],
    })


async def _validate(
    sat: dict[str, Any] | None = None, unique: list[str] | None = None, *, strip: bool = False,
) -> tuple[list[Any], VaultAgentState]:
    bom = _bom(unique or [*KEYS, "StartDate"])
    state = VaultAgentState(source_schemas=[PRODUCT, UNIT, bom])
    for column in KEYS:
        state.link_proposals.licenses.append(KeyLicense(
            source_table="BillOfMaterials", source_column=column, references_table="Product",
            references_column="ProductID", references_schema="Production",
            ratification_status="accepted",
        ))
    state.dv_model = apply_key_licenses(_delta(sat or {}), DVModel(), state)
    await CodeGeneratorAgent().run(state)
    if strip:  # the metadata as a run before WP133 stored it
        for join in state.artifacts.automatedv_yaml["staging"][STAGE]["key_translation"]["joins"]:
            del join["reads"]
    await ValidatorAgent().run(state)
    return [i for i in state.validation_report.issues if i.code == CODE], state


async def test_the_bill_of_materials_satellite_is_refused_through_its_translation() -> None:
    [issue], _ = await _validate()
    assert issue.construct == SAT and issue.severity == "error"
    assert "BillOfMaterials" in issue.message and "StartDate" in issue.message
    assert "PRODUCTASSEMBLYID" in issue.message and "PRODUCTNUMBER" not in issue.message
    assert issue.remedy and "multi_active" in issue.remedy and "StartDate" in issue.remedy


async def test_the_stage_says_which_column_each_translated_key_stands_for() -> None:
    _, state = await _validate()
    joins = state.artifacts.automatedv_yaml["staging"][STAGE]["key_translation"]["joins"]
    assert {j["projects"]: j["reads"] for j in joins} == {
        "PRODUCTNUMBER": "PRODUCTASSEMBLYID", "COMPONENT_PRODUCTNUMBER": "COMPONENTID",
    }


# ── what stays as it was (green before and after) ───────────────────────────────────────────
async def test_the_remedy_followed_passes() -> None:
    issues, _ = await _validate({"sat_type": "multi_active",
                                 "child_dependent_key": ["StartDate"]})
    assert issues == []


async def test_a_translated_key_that_covers_the_unique_key_passes() -> None:
    issues, _ = await _validate(unique=list(KEYS))
    assert issues == []


async def test_metadata_without_the_typed_column_is_not_judged() -> None:
    issues, _ = await _validate(strip=True)
    assert issues == []
