"""WP55 — a link with one hub is that hub's satellite feed (spec §3). Committed before the
change, failing. The fixture is the eighth chain's step-5 attempt-1 shape."""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from vault_agent import llm
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import flag_role
from vault_agent.state import FlagKind, VaultAgentState

LINK = "link_sales_representative_quota_history"
SAT = "sat_sales_representative_quota_details"


def _payload(hub: str = "hub_employee", with_relation: bool = True,
             extra_sats: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sat: dict[str, Any] = {
        "name": SAT, "parent": LINK, "attributes": ["QuotaDate", "SalesQuota", "ModifiedDate"],
        "description": "The dated quota amount in force for a representative.",
    }
    if with_relation:
        sat["source_table"] = "SalesPersonQuotaHistory"
    return {
        "hubs": [{"name": "hub_employee", "business_key": "NationalIDNumber",
                  "source_entity": "Employee", "description": "An employee."}],
        "links": [{"name": LINK, "connected_hubs": [hub],
                   "description": "The full history of sales quotas per representative."}],
        "satellites": [sat, *(extra_sats or [])],
    }


async def _run(payload: dict[str, Any]) -> tuple[VaultAgentState, list[llm.TraceEvent]]:
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(_state())
    finally:
        llm.set_trace_recorder(None)
    return state, events


async def test_a_one_hub_link_collapses_into_the_hub_and_its_satellite_moves_there() -> None:
    state, events = await _run(_payload())
    assert state.dv_model.links == []
    [sat] = state.dv_model.satellites
    assert sat.name == SAT and sat.parent == "hub_employee"
    assert sat.attributes == ["QuotaDate", "SalesQuota", "ModifiedDate"]
    assert sat.source_table == "SalesPersonQuotaHistory"
    [flag] = [f for f in state.flags if f.kind == FlagKind.LINK_COLLAPSED]
    assert flag.asset == SAT and LINK in flag.message and "hub_employee" in flag.message
    assert not [f for f in state.flags if f.kind == FlagKind.DROPPED_RECORD]
    [event] = [e for e in events if e.kind == "backstop" and e.backstop_id == "one_hub_link_collapsed"]
    assert event.detail == {"link": LINK, "hub": "hub_employee", "satellites": [SAT]}


async def test_a_one_hub_link_to_an_unknown_hub_is_dropped_as_before() -> None:
    state, events = await _run(_payload(hub="hub_nobody"))
    assert state.dv_model.links == [] and state.dv_model.satellites == []
    dropped = sorted(f.asset for f in state.flags if f.kind == FlagKind.DROPPED_RECORD)
    assert dropped == [LINK, SAT]
    assert not [f for f in state.flags if f.kind == FlagKind.LINK_COLLAPSED]
    assert not [e for e in events if e.kind == "backstop"]


async def test_a_satellite_without_a_relation_is_dropped_while_its_sibling_moves() -> None:
    bare = {"name": "sat_quota_notes", "parent": LINK, "attributes": ["Notes"],
            "description": "No relation declared."}
    state, _ = await _run(_payload(extra_sats=[bare]))
    assert [s.name for s in state.dv_model.satellites] == [SAT]
    assert [f.asset for f in state.flags if f.kind == FlagKind.DROPPED_RECORD] == ["sat_quota_notes"]
    assert [f.asset for f in state.flags if f.kind == FlagKind.LINK_COLLAPSED] == [SAT]


def test_link_collapsed_is_a_disclosure() -> None:
    assert flag_role(FlagKind.LINK_COLLAPSED) == "disclosure"
