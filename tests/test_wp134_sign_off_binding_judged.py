"""WP134 (C70) — a binding made at sign-off is judged by the gates that read a stage's relation.
Written FIRST. The validator runs before the sign-off, so a stage a human binds there was unbound
when the column gate (WP73) and the satellite grain gate (WP85) looked. The sign-off's own check
never looked at grain — the demo's first chain (2026-11-15) bound `stg_work_order_operation` to
`WorkOrderRouting`, whose key the stage's satellite does not cover, and nobody was told — and it
still demanded a translated stage's projected keys from the relation, which WP132 had stopped
doing in the validator. Keyless."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.bindings import check_stage_bindings, pending_stage_bindings
from vault_agent.state import DVModel, SourceTable, StageBinding, VaultAgentState

STAGE = "stg_work_order_operation"
SAT = "sat_work_order_operation_details"
ROUTING_KEY = ["WorkOrderID", "ProductID", "OperationSequence"]


def _routing(primary_key: list[str] | None = None, **renamed: str) -> SourceTable:
    columns = ["WorkOrderID", "ProductID", "OperationSequence", "LocationID", "PlannedCost"]
    return SourceTable(
        table="WorkOrderRouting", schema="Production",
        columns=[renamed.get(c, c) for c in columns],
        primary_key=ROUTING_KEY if primary_key is None else primary_key,
    )


def _stage() -> dict[str, Any]:
    # The stage as the first chain's third step stored it, without its payload's hex columns.
    return {
        "source_model": {"inferred": "raw_work_order_operation"},
        "source_binding": "inferred",
        "hashed_columns": {
            "WORKORDERROUTING_HK": ["WORKORDERID", "OPERATIONSEQUENCE"],
            "WORK_ORDER_OPERATION_DETAILS_HASHDIFF": {"columns": ["PLANNEDCOST"],
                                                      "is_hashdiff": True},
        },
    }


def _satellite(**extra: Any) -> dict[str, Any]:
    return {"source_model": STAGE, "src_pk": "WORKORDERROUTING_HK",
            "src_hashdiff": "WORK_ORDER_OPERATION_DETAILS_HASHDIFF",
            "src_payload": ["PLANNEDCOST"], **extra}


def _state(
    table: SourceTable | None = None, satellite: dict[str, Any] | None = None,
    stage: dict[str, Any] | None = None,
) -> VaultAgentState:
    state = VaultAgentState(source_schemas=[table or _routing()])
    state.artifacts.automatedv_yaml = {
        "staging": {STAGE: stage or _stage()},
        "satellites": {SAT: satellite or _satellite()},
    }
    return state


def _check(state: VaultAgentState, columns: dict[str, str] | None = None) -> list[str]:
    binding = StageBinding(relation="WorkOrderRouting", columns=columns or {})
    return check_stage_bindings(state, {STAGE: binding})


# ── the grain judgement at sign-off ────────────────────────────────────────────────────────────

def test_a_binding_whose_satellite_does_not_cover_the_relations_key_is_refused() -> None:
    [error] = _check(_state())
    assert error.startswith(f"{STAGE}:")
    assert SAT in error and "ProductID" in error and "E_SAT_GRAIN_NOT_UNIQUE" in error
    assert "WorkOrderID + ProductID + OperationSequence" in error


def test_the_refused_binding_is_not_applied() -> None:
    state = _state()
    apply_human_decision(
        state, {"bindings": {STAGE: {"relation": "WorkOrderRouting"}}, "accept": True}
    )
    assert state.ratified_bindings == {}


def test_a_key_that_covers_the_relations_key_is_bound() -> None:
    assert _check(_state(_routing(["WorkOrderID", "OperationSequence"]))) == []


def test_a_multi_active_satellite_on_the_missing_column_is_bound() -> None:
    assert _check(_state(satellite=_satellite(src_cdk=["PRODUCTID"]))) == []


def test_a_relation_without_a_declared_key_is_not_judged() -> None:
    assert _check(_state(_routing([]))) == []


def test_a_satellite_of_the_vault_being_extended_is_not_judged() -> None:
    state = _state()
    state.existing_model = DVModel.model_validate({
        "hubs": [{"name": "hub_work_order_operation", "business_key": "work_order_operation",
                  "source_entity": "WorkOrderRouting", "description": "An operation."}],
        "satellites": [{"name": SAT, "parent": "hub_work_order_operation",
                        "attributes": ["PlannedCost"], "description": "Costs."}],
    })
    assert _check(state) == []


def test_an_effectivity_satellite_is_not_judged() -> None:
    assert _check(_state(satellite=_satellite(src_dfk=["WORKORDERROUTING_HK"]))) == []


def test_an_alias_of_the_binding_is_read_as_the_relations_column() -> None:
    # The relation calls the sequence `Seq`; the human says so. The satellite's key then covers
    # (WorkOrderID, Seq) — judged through the alias, not by the stage's own name for it.
    table = _routing(["WorkOrderID", "Seq"], OperationSequence="Seq")
    assert _check(_state(table), {"OPERATIONSEQUENCE": "Seq"}) == []
    [error] = _check(_state(_routing(OperationSequence="Seq")), {"OPERATIONSEQUENCE": "Seq"})
    assert "E_SAT_GRAIN_NOT_UNIQUE" in error and "ProductID" in error


# ── a stage that reads through a translation view ──────────────────────────────────────────────

BOM_STAGE = "stg_product_assembly_component"
BOM_SAT = "sat_product_assembly_component_details"


def _bom(unique: list[str], *, without: str | None = None) -> SourceTable:
    columns = ["BillOfMaterialsID", "ProductAssemblyID", "ComponentID", "StartDate",
               "UnitMeasureCode", "PerAssemblyQty"]
    return SourceTable(
        table="BillOfMaterials", schema="Production",
        columns=[c for c in columns if c != without],
        primary_key=["BillOfMaterialsID"], unique_keys=[unique],
    )


def _bom_state(table: SourceTable, satellite: dict[str, Any] | None = None) -> VaultAgentState:
    join = {"through_table": "Product", "on": "… = PRODUCTID"}
    state = VaultAgentState(source_schemas=[table])
    state.artifacts.automatedv_yaml = {
        "staging": {BOM_STAGE: {
            "source_model": {"inferred": "raw_product_assembly_component"},
            "source_binding": "inferred",
            "hashed_columns": {
                "PRODUCT_HK": "PRODUCTNUMBER",
                "COMPONENT_PRODUCT_HK": "COMPONENT_PRODUCTNUMBER",
                "UNITMEASURE_HK": "UNITMEASURECODE",
                "LINK_PRODUCT_ASSEMBLY_COMPONENT_HK": [
                    "PRODUCTNUMBER", "COMPONENT_PRODUCTNUMBER", "UNITMEASURECODE"],
            },
            "key_translation": {"model": "stg_product_assembly_component_via_product", "joins": [
                {**join, "projects": "PRODUCTNUMBER", "reads": "PRODUCTASSEMBLYID"},
                {**join, "projects": "COMPONENT_PRODUCTNUMBER", "reads": "COMPONENTID"},
            ]},
        }},
        "satellites": {BOM_SAT: satellite or {
            "source_model": BOM_STAGE, "src_pk": "LINK_PRODUCT_ASSEMBLY_COMPONENT_HK",
            "src_cdk": ["STARTDATE"], "src_payload": ["PERASSEMBLYQTY"],
        }},
    }
    return state


def _check_bom(state: VaultAgentState) -> list[str]:
    return check_stage_bindings(state, {BOM_STAGE: StageBinding(relation="BillOfMaterials")})


UNIQUE = ["ProductAssemblyID", "ComponentID", "StartDate"]


def test_a_translated_stage_is_bound_to_the_relation_that_carries_what_it_reads() -> None:
    # The relation has no product number and needs none: the view projects it (WP132's reading).
    assert _check_bom(_bom_state(_bom(UNIQUE))) == []


def test_a_relation_without_the_translations_referencing_column_is_refused_by_its_name() -> None:
    [error] = _check_bom(_bom_state(_bom(UNIQUE, without="ComponentID")))
    assert "COMPONENTID" in error and "PRODUCTNUMBER" not in error


def test_a_translated_stages_satellite_is_grain_judged_through_what_the_keys_stand_for() -> None:
    satellite = {"source_model": BOM_STAGE, "src_pk": "LINK_PRODUCT_ASSEMBLY_COMPONENT_HK",
                 "src_payload": ["PERASSEMBLYQTY"]}
    [error] = _check_bom(_bom_state(_bom(UNIQUE), satellite))
    assert BOM_SAT in error and "StartDate" in error and "E_SAT_GRAIN_NOT_UNIQUE" in error


def test_the_checkpoint_asks_the_relation_for_what_the_stage_reads_from_it() -> None:
    [pending] = pending_stage_bindings(_bom_state(_bom(UNIQUE)))
    assert pending["expected_columns"] == ["UNITMEASURECODE", "PRODUCTASSEMBLYID", "COMPONENTID"]
