"""A model that double-encodes an object-valued tool field must not take a paid run down.

Found on 2026-09-17 by a paid `bank_extension` repeat: `emit_mapping` returned
``{"mappings": "{\\n  \\"crm_campaign::campaign_code\\": {...}"}`` — the object as a JSON STRING —
and `merge_decisions` called `.items()` on it. `AttributeError: 'str' object has no attribute
'items'` propagated out of the agent and killed the run: five completed pipeline stages and their
tokens, thrown away by one malformed field.

* ``test_the_mapper_survives_a_stringified_mappings_object`` — FLIPPED by the backstop; pinned
  here as the crash.
* ``test_a_well_formed_payload_is_unaffected`` — never flipped.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from vault_agent.agents.source_mapper import SourceMapperAgent
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
    """Pinned today: the run dies. To flip: the decisions are decoded and the mapping proposed."""
    agent = SourceMapperAgent(_Stub({"mappings": json.dumps(_DECISIONS)}))

    with pytest.raises(AttributeError):
        await agent.run(_state())


async def test_a_well_formed_payload_is_unaffected() -> None:
    state = await SourceMapperAgent(_Stub({"mappings": _DECISIONS})).run(_state())

    assert [(p.concept, p.table, p.column) for p in state.mappings.proposals] == [
        ("national customer ID", "raw_customer", "NATIONAL_CUSTOMER_ID")
    ]
