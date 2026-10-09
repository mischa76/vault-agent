"""WP63 — the declared column type decides a contract field's type (spec §3). Committed before
the change, failing."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.data_contract import DataContractAgent
from vault_agent.rules.dv2_rules import json_type_for_sql
from vault_agent.state import FlagKind, SourceTable, VaultAgentState


def test_sql_server_base_types_map_and_user_defined_types_do_not() -> None:
    assert json_type_for_sql("int") == "integer"
    assert json_type_for_sql("nvarchar(50)") == "string"
    assert json_type_for_sql("money") == "number"
    assert json_type_for_sql("bit") == "boolean"
    assert json_type_for_sql("datetime") == "string"
    assert json_type_for_sql("Name") is None
    assert json_type_for_sql("") is None


def _state() -> VaultAgentState:
    return VaultAgentState(source_schemas=[
        SourceTable(table="BusinessEntityAddress", columns=[
            {"name": "BusinessEntityID", "type": "int"},
            {"name": "ModifiedDate", "type": "datetime"},
            {"name": "Style", "type": "NameStyle"},  # a user-defined type
            "FreeText",  # a bare name: no type declared
            "Mystery",
        ]),
    ])


def _enrichment(**types: Any) -> dict[str, Any]:
    return {"fields": {k: {"description": k, "data_type": v} for k, v in types.items()}}


def test_declared_types_decide_and_the_model_fills_only_gaps() -> None:
    state = _state()
    contract = DataContractAgent()._build_contract(
        "BusinessEntityAddress",
        ["BusinessEntityID", "ModifiedDate", "Style", "FreeText", "Mystery"],
        set(),
        _enrichment(BusinessEntityID="unknown", ModifiedDate="unknown", Style="boolean",
                    FreeText="integer", Mystery="unknown"),
        grounded=True, state=state,
    )
    types = {f.name: f.constraints.data_type for f in contract.fields}
    assert types == {
        "BusinessEntityID": "integer",  # declared int beats the model's unknown
        "ModifiedDate": "string",  # declared datetime
        "Style": "boolean",  # a user-defined type: the model's answer counts
        "FreeText": "integer",  # no declared type: the model's answer counts
        "Mystery": "unknown",  # no declared type, no answer
    }
    flagged = [f.asset for f in state.flags if f.kind == FlagKind.UNDETERMINED_TYPE]
    assert flagged == ["BusinessEntityAddress.Mystery"]
