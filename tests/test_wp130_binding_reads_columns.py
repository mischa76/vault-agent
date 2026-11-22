"""WP130 (C66) — a sign-off binding is checked against the columns a stage reads, not against
the text of a generator expression. Written FIRST. Since WP123 a hashdiff reads derived columns
whose value is an expression (`ENCODE(CONVERT_TO(…ACTUALCOST…), 'hex')`); `stage_key_needs` took
that text for a column name, so every binding of a stage with a hashdiff was refused — found at
the sign-off of the demo's chain (2026-11-15), the stage below. Keyless."""
from __future__ import annotations

from typing import Any

from vault_agent.bindings import check_stage_bindings, pending_stage_bindings, stage_key_needs
from vault_agent.state import SourceTable, StageBinding, VaultAgentState

HEX = "ENCODE(CONVERT_TO(NULLIF(TRIM(CAST({} AS text)), ''), 'UTF8'), 'hex')"
# The stage as the chain's metadata stored it, two of its eight payload columns.
STAGE: dict[str, Any] = {
    "source_model": "raw_work_order_operation",
    "source_binding": "inferred",
    "derived_columns": {
        "ACTUALCOST__CS": HEX.format("ACTUALCOST"),
        "PLANNEDCOST__CS": HEX.format("PLANNEDCOST"),
    },
    "expression_reads": {"ACTUALCOST__CS": ["ACTUALCOST"], "PLANNEDCOST__CS": ["PLANNEDCOST"]},
    "hashed_columns": {
        "WORKORDERROUTING_HK": ["WORKORDERID", "OPERATIONSEQUENCE"],
        "WORK_ORDER_OPERATION_DETAILS_HASHDIFF": {
            "columns": ["PLANNEDCOST__CS", "ACTUALCOST__CS"], "is_hashdiff": True,
        },
    },
}
ROUTING = SourceTable(
    table="WorkOrderRouting", schema="Production",
    columns=["WorkOrderID", "ProductID", "OperationSequence", "LocationID", "PlannedCost",
             "ActualCost"],
)


def _state(table: SourceTable = ROUTING) -> VaultAgentState:
    state = VaultAgentState(source_schemas=[table])
    state.artifacts.automatedv_yaml = {"staging": {"stg_work_order_operation": STAGE}}
    return state


def test_the_needs_are_columns_never_expression_text() -> None:
    needs = stage_key_needs(STAGE)
    assert needs == ["WORKORDERID", "OPERATIONSEQUENCE", "ACTUALCOST", "PLANNEDCOST"]
    assert not [n for n in needs if "(" in n]


def test_a_role_alias_is_still_read_by_its_source_column() -> None:
    # WP82's own case, unchanged: a derived column without an expression names its source.
    meta = {"hashed_columns": {"STORE_HK": "STOREID"},
            "derived_columns": {"STOREID": "BUSINESSENTITYID"}}
    assert stage_key_needs(meta) == ["BUSINESSENTITYID"]


def test_a_stage_with_a_hashdiff_can_be_bound_to_the_relation_that_carries_its_columns() -> None:
    binding = {"stg_work_order_operation": StageBinding(relation="WorkOrderRouting")}
    assert check_stage_bindings(_state(), binding) == []


def test_a_relation_without_a_payload_column_is_still_refused_by_the_columns_name() -> None:
    short = SourceTable(table="WorkOrderRouting", schema="Production",
                        columns=["WorkOrderID", "OperationSequence", "PlannedCost"])
    [error] = check_stage_bindings(
        _state(short), {"stg_work_order_operation": StageBinding(relation="WorkOrderRouting")}
    )
    assert "ACTUALCOST" in error and "ENCODE" not in error


def test_the_checkpoint_names_columns_to_the_human() -> None:
    [pending] = pending_stage_bindings(_state())
    assert pending["expected_columns"] == [
        "WORKORDERID", "OPERATIONSEQUENCE", "ACTUALCOST", "PLANNEDCOST",
    ]
