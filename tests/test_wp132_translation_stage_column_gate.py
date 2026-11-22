"""WP132 (C68) — a stage that reads through a translation view is column-checked: against its
relation's columns plus what the view projects — by the validator's gate and where a binding is
made. Written FIRST. WP73 skipped every such stage in both places; since WP125 they are the
ordinary case (45 of 177 stages in the demo of 2026-11-15), and the demo's bill-of-materials
stage — a `PRODUCTNUMBER` neither `BillOfMaterials` nor its view carries — was bound by the
mapper's re-bind, passed every gate and was refused by PostgreSQL. Keyless."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.staging_generator import StagingSpec, bind_sources
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import DVModel, FlagKind, KeyTranslation, SourceTable, VaultAgentState

CODE = "E_STAGE_COLUMN_NOT_IN_SOURCE"
HEX = "ENCODE(CONVERT_TO(NULLIF(TRIM(CAST({} AS text)), ''), 'UTF8'), 'hex')"
BOM = SourceTable(
    table="BillOfMaterials", schema="Production",
    columns=["BillOfMaterialsID", "ProductAssemblyID", "ComponentID", "UnitMeasureCode",
             "StartDate", "PerAssemblyQty"],
)
RATE = SourceTable(table="SalesOrderHeader", schema="Sales",
                   columns=["SalesOrderID", "CurrencyRateID"])
COMPONENT_JOIN = {"through_table": "Product", "on": "COMPONENTID = PRODUCTID",
                  "projects": "COMPONENT_PRODUCTNUMBER"}
ASSEMBLY_JOIN = {"through_table": "Product", "on": "PRODUCTASSEMBLYID = PRODUCTID",
                 "projects": "PRODUCTNUMBER"}


def _bom_stage(*joins: dict[str, Any]) -> dict[str, Any]:
    """The stage as the demo's chain stored it (one payload column of three)."""
    return {
        "source_model": {"raw_5": "BillOfMaterials"},
        "source_binding": "declared",
        "derived_columns": {"APPLIED_DTS": "STARTDATE",
                            "PERASSEMBLYQTY__CS": HEX.format("PERASSEMBLYQTY")},
        "expression_reads": {"PERASSEMBLYQTY__CS": ["PERASSEMBLYQTY"]},
        "hashed_columns": {
            "COMPONENT_PRODUCT_HK": "COMPONENT_PRODUCTNUMBER",
            "LINK_PRODUCT_ASSEMBLY_COMPONENT_HK": [
                "PRODUCTNUMBER", "COMPONENT_PRODUCTNUMBER", "UNITMEASURECODE"],
            "PRODUCT_ASSEMBLY_COMPONENT_DETAILS_HASHDIFF": {
                "columns": ["PERASSEMBLYQTY__CS"], "is_hashdiff": True},
            "PRODUCT_HK": "PRODUCTNUMBER",
            "UNITMEASURE_HK": "UNITMEASURECODE",
        },
        "key_translation": {"model": "stg_product_assembly_component_via_product",
                            "joins": list(joins)},
    }


async def _issues(staging: dict[str, dict[str, Any]]) -> list[Any]:
    state = VaultAgentState(source_schemas=[BOM, RATE], dv_model=DVModel.model_validate({
        "hubs": [{"name": "hub_product", "business_key": "ProductNumber",
                  "source_entity": "Product", "description": "x"}],
        "links": [], "satellites": []}))
    state.artifacts.automatedv_yaml = {"staging": staging}
    await ValidatorAgent().run(state)
    return [i for i in state.validation_report.issues if i.code == CODE]


async def test_the_demos_stage_is_refused_for_the_key_nothing_carries() -> None:
    [issue] = await _issues({"stg_product_assembly_component": _bom_stage(COMPONENT_JOIN)})
    assert issue.construct == "stg_product_assembly_component" and issue.severity == "error"
    assert "PRODUCTNUMBER" in issue.message and "BillOfMaterials" in issue.message
    assert "stg_product_assembly_component_via_product" in issue.message
    assert "COMPONENT_PRODUCTNUMBER" not in issue.message.replace(
        "projects COMPONENT_PRODUCTNUMBER", "")


async def test_a_stage_whose_view_projects_every_translated_key_passes() -> None:
    assert await _issues(
        {"stg_product_assembly_component": _bom_stage(ASSEMBLY_JOIN, COMPONENT_JOIN)}
    ) == []


async def test_a_composite_keys_projection_counts_column_by_column() -> None:
    stage = {
        "source_model": {"raw": "SalesOrderHeader"}, "source_binding": "declared",
        "hashed_columns": {"SALESORDER_HK": "SALESORDERID",
                           "CURRENCYRATE_HK": ["CURRENCYRATEDATE", "FROMCURRENCYCODE"]},
        "key_translation": {"model": "stg_x_via_currency_rate", "joins": [{
            "through_table": "CurrencyRate", "on": "CURRENCYRATEID = CURRENCYRATEID",
            "projects": ["CURRENCYRATEDATE", "FROMCURRENCYCODE"]}]},
    }
    assert await _issues({"stg_x": stage}) == []
    stage["hashed_columns"]["CURRENCYRATE_HK"].append("TOCURRENCYCODE")
    [issue] = await _issues({"stg_x": stage})
    assert "TOCURRENCYCODE" in issue.message and "FROMCURRENCYCODE" not in issue.message.split(
        "carries", 1)[-1]


async def test_an_inferred_stage_is_still_not_judged() -> None:
    stage = _bom_stage(COMPONENT_JOIN) | {"source_binding": "inferred",
                                          "source_model": "raw_product_assembly_component"}
    assert await _issues({"stg_product_assembly_component": stage}) == []


def test_the_projection_is_read_from_the_typed_field() -> None:
    from vault_agent.bindings import translation_projects  # new with WP132

    assert translation_projects(_bom_stage(ASSEMBLY_JOIN, COMPONENT_JOIN)) == [
        "PRODUCTNUMBER", "COMPONENT_PRODUCTNUMBER"]
    assert translation_projects({"hashed_columns": {}}) == []


# ── where a binding is made (the mapper's re-bind runs after the validator) ─────────────────
def _spec(*columns: str) -> StagingSpec:
    """The bill of materials' stage; ``columns`` are the referencing columns translated."""
    spec = StagingSpec(name="stg_product_assembly_component", base="product_assembly_component")
    spec.add_hashed("PRODUCT_HK", "PRODUCTNUMBER")
    spec.add_hashed("COMPONENT_PRODUCT_HK", "COMPONENT_PRODUCTNUMBER")
    spec.add_hashed("UNITMEASURE_HK", "UNITMEASURECODE")
    projects = {"ProductAssemblyID": "PRODUCTNUMBER", "ComponentID": "COMPONENT_PRODUCTNUMBER"}
    for column in columns:
        spec.add_translation(KeyTranslation(
            referencing_column=column, through_table="Product", through_schema="Production",
            surrogate_column="ProductID", natural_key_column="PRODUCTNUMBER",
        ), projects[column])
    return spec


OVERRIDE = {normalize_identifier("product_assembly_component"): "BillOfMaterials"}


def test_a_binding_is_refused_when_neither_relation_nor_view_carries_a_key() -> None:
    spec = _spec("ComponentID")
    flags = bind_sources({"a": spec}, [BOM], source_overrides=OVERRIDE)
    assert not spec.bound and spec.source_model == "raw_product_assembly_component"
    [flag] = [f for f in flags if f.kind == FlagKind.BINDING_REJECTED]
    assert flag.asset == spec.name and flag.reason == "BillOfMaterials"
    assert "PRODUCTNUMBER" in flag.message
    assert "COMPONENT_PRODUCTNUMBER" not in flag.message


def test_a_binding_holds_when_the_view_projects_every_translated_key() -> None:
    spec = _spec("ProductAssemblyID", "ComponentID")
    flags = bind_sources({"a": spec}, [BOM], source_overrides=OVERRIDE)
    assert spec.bound and spec.source_model == "BillOfMaterials"
    assert flags == []
