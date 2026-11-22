"""A model that double-encodes an object-valued tool field must not take a paid run down.

Found on 2026-09-17 by a paid `bank_extension` repeat: `emit_mapping` returned
``{"mappings": "{\\n  \\"crm_campaign::campaign_code\\": {...}"}`` — the object as a JSON STRING —
and `merge_decisions` called `.items()` on it. `AttributeError: 'str' object has no attribute
'items'` propagated out of the agent and killed the run: five completed pipeline stages and their
tokens, thrown away by one malformed field.

* ``test_the_mapper_survives_a_stringified_mappings_object`` — FLIPPED by the backstop; pinned at
  5a26cdc as the crash.
* ``test_a_well_formed_payload_is_unaffected`` — never flipped.
* The `decoded_field` cases below cover the other four call sites (`emit_resolution`,
  `emit_contract_enrichment`, `emit_requirements`, `emit_business_keys`), the telemetry, and the
  two shapes it refuses to repair.
"""
from __future__ import annotations

import json
from typing import Any

from vault_agent.agents.source_mapper import SourceMapperAgent
from vault_agent.llm import TraceEvent, decoded_field
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    Hub,
    SourceTable,
    VaultAgentState,
)

_DECISIONS = {
    "national customer ID": {
        "decision": "map", "table": "raw_customer", "column": "NATIONAL_CUSTOMER_ID",
        "confidence": 0.95, "evidence": ["column comment names it"],
    }
}


class _Stub:
    """The mapper's LLM seam, answering with a payload the model actually produced."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]:
        return self.payload.get("mappings", {})  # type: ignore[no-any-return]


def _state() -> VaultAgentState:
    return VaultAgentState(
        dv_model=DVModel(hubs=[Hub(name="hub_customer", business_key="national customer ID",
                                   source_entity="customer", description="A customer.")]),
        source_schemas=[SourceTable(table="raw_customer",
                                    columns=["NATIONAL_CUSTOMER_ID", "CUST_NAME"])],
        business_keys=[BusinessKeyCandidate(entity="customer", field="national customer ID",
                                            score=0.9, rationale="r")],
    )


async def test_the_mapper_survives_a_stringified_mappings_object() -> None:
    """Flipped by the backstop (pinned at 5a26cdc as: AttributeError out of the agent)."""
    agent = SourceMapperAgent(_Stub({"mappings": json.dumps(_DECISIONS)}))

    state = await agent.run(_state())

    assert [(p.concept, p.table, p.column) for p in state.mappings.proposals] == [
        ("national customer ID", "raw_customer", "NATIONAL_CUSTOMER_ID")
    ]


async def test_a_well_formed_payload_is_unaffected() -> None:
    state = await SourceMapperAgent(_Stub({"mappings": _DECISIONS})).run(_state())

    assert [(p.concept, p.table, p.column) for p in state.mappings.proposals] == [
        ("national customer ID", "raw_customer", "NATIONAL_CUSTOMER_ID")
    ]

_MAPPINGS = {
    "crm_campaign::campaign_code": {
        "decision": "map", "table": "crm_campaign", "column": "campaign_code",
        "confidence": 0.99, "evidence": ["column comment names the campaign code"],
    }
}


def _recorded() -> tuple[list[TraceEvent], Any]:
    events: list[TraceEvent] = []
    return events, events.append


def test_a_stringified_mapping_object_is_decoded() -> None:
    events, recorder = _recorded()
    payload = {"mappings": json.dumps(_MAPPINGS)}

    out = decoded_field(payload, "mappings", {}, tool_name="emit_mapping", recorder=recorder)

    assert out == _MAPPINGS
    [event] = events
    assert event.kind == "backstop" and event.backstop_id == "stringified_payload_field"
    assert event.detail == {"tool": "emit_mapping", "field": "mappings", "as": "dict"}


def test_a_stringified_resolution_object_is_decoded() -> None:
    payload = {"resolutions": json.dumps({"customer::id": {"resolution": "hub_customer"}})}
    assert decoded_field(payload, "resolutions", {}) == {
        "customer::id": {"resolution": "hub_customer"}
    }


def test_a_stringified_contract_object_is_decoded() -> None:
    payload = {"assets": json.dumps({"crm_contact": {"doc": "CRM contacts."}})}
    assert decoded_field(payload, "assets", {}) == {"crm_contact": {"doc": "CRM contacts."}}


def test_a_stringified_requirements_list_is_decoded() -> None:
    payload = {"requirements": json.dumps([{"id": "REQ-1", "text": "t", "category": "functional"}])}
    assert decoded_field(payload, "requirements", []) == [
        {"id": "REQ-1", "text": "t", "category": "functional"}
    ]


def test_a_stringified_business_keys_list_is_decoded() -> None:
    payload = {"business_keys": json.dumps([{"entity": "customer", "field": "id", "score": 0.9}])}
    assert decoded_field(payload, "business_keys", []) == [
        {"entity": "customer", "field": "id", "score": 0.9}
    ]


def test_a_well_formed_payload_is_untouched() -> None:
    events, recorder = _recorded()

    out = decoded_field({"mappings": _MAPPINGS}, "mappings", {}, recorder=recorder)

    assert out == _MAPPINGS and events == []


def test_undecodable_text_yields_the_empty_default() -> None:
    events, recorder = _recorded()

    assert decoded_field({"mappings": "sorry, no mappings"}, "mappings", {},
                         recorder=recorder) == {}
    # A list where an object belongs is not a shape this repairs either.
    assert decoded_field({"mappings": json.dumps([1, 2])}, "mappings", {}) == {}
    assert events == []


def test_a_missing_field_yields_the_empty_default() -> None:
    assert decoded_field({}, "mappings", {}) == {}
    assert decoded_field({"mappings": None}, "mappings", {}) == {}
