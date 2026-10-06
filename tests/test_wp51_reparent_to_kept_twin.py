"""WP51 — a dropped hub's payload moves to its kept twin (spec §3). Committed before the change,
failing. The fixture is step 2 attempt 1 of the fifth chain (`20261006T032619166848Z`): two
collisions, their kept twins, and the satellites and links that hung on the dropped hubs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from tests.test_collision_remedy_guard import CANDIDATES, _business_entity, _vendor, _vendor_be
from vault_agent import llm
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import DVModel, FlagKind, RetiredConstruct, VaultAgentState

_FIXTURE = Path(__file__).parent / "fixtures" / "wp51" / "step2_attempt1_twins.json"


def _payload() -> dict[str, Any]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {k: data[k] for k in ("hubs", "links", "satellites")}


def _retirements(*, with_twins: bool = True) -> list[RetiredConstruct]:
    """What attempt 1's validator recorded for the two collisions."""
    return [
        RetiredConstruct(
            name="hub_employee_business_entity", kind="hub", code="E_HUB_HK_COLLISION", attempt=1,
            source_entity="Employee", key_columns=["BUSINESSENTITYID"],
            kept_twin="hub_employee" if with_twins else None,
        ),
        RetiredConstruct(
            name="hub_job_candidate", kind="hub", code="E_HUB_HK_COLLISION", attempt=1,
            source_entity="JobCandidate", key_columns=["JOBCANDIDATEID"],
            kept_twin="hub_candidate_business_entity" if with_twins else None,
        ),
    ]


# --- Guard 1: the retirement knows the twin --------------------------------------------------


async def test_the_validator_records_the_kept_twin_of_a_collision() -> None:
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_business_entity(), _vendor(), _vendor_be()]),
        business_keys=CANDIDATES,
        modeling_attempts=1,
    )
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == "E_HUB_HK_COLLISION"]
    assert issue.retires_into == "hub_vendor"
    [retired] = state.retired_constructs
    assert retired.name == "hub_vendor_business_entity" and retired.kept_twin == "hub_vendor"


# --- Guard 2: the memory moves the payload instead of orphaning it ---------------------------


async def test_dependents_of_a_dropped_hub_move_to_its_kept_twin() -> None:
    state = _state()
    state.retired_constructs = _retirements()
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    finally:
        llm.set_trace_recorder(None)

    hubs = {h.name for h in state.dv_model.hubs}
    assert {"hub_employee", "hub_candidate_business_entity"} <= hubs
    assert not {"hub_employee_business_entity", "hub_job_candidate"} & hubs

    sats = {s.name: s for s in state.dv_model.satellites}
    assert sats["sat_job_candidate_details"].parent == "hub_candidate_business_entity"
    assert sats["sat_employee_pay_rate"].parent == "hub_employee"
    assert sats["sat_employee_pay_rate"].sat_type == "multi_active"  # untouched but for the parent
    # The twin's own satellite is still there; the dropped link's satellites went with the link.
    assert "sat_employee_profile" in sats
    assert "sat_employee_assignment_eff" in sats and "sat_employee_assignment_details" in sats

    links = {lk.name: lk for lk in state.dv_model.links}
    assert [r.hub for r in links["link_employee_assignment"].hub_refs] == [
        "hub_employee", "hub_department", "hub_shift"
    ]
    assert "link_candidate_employee" not in links  # the twin already took part: a self-link

    kinds = {k: sorted(f.asset for f in state.flags if f.kind == k)
             for k in (FlagKind.RETIRED_REPARENTED, FlagKind.RETIRED_ORPHAN, FlagKind.RETIRED_REEMITTED)}
    assert kinds[FlagKind.RETIRED_REPARENTED] == [
        "link_employee_assignment", "sat_employee_pay_rate", "sat_job_candidate_details"
    ]
    assert kinds[FlagKind.RETIRED_ORPHAN] == ["link_candidate_employee"]
    assert kinds[FlagKind.RETIRED_REEMITTED] == ["hub_employee_business_entity", "hub_job_candidate"]
    [event] = [e for e in events if e.kind == "backstop"]
    assert sorted(event.detail["reparented"]) == kinds[FlagKind.RETIRED_REPARENTED]


# --- Guard 3: the result passes the collision gate and the twin has its satellite ------------


async def test_the_repaired_model_has_no_collision_and_the_twin_keeps_the_payload() -> None:
    state = _state()
    state.retired_constructs = _retirements()
    state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    await ValidatorAgent().run(state)
    assert not [i for i in state.validation_report.issues if i.code == "E_HUB_HK_COLLISION"]
    twin_sats = [s.name for s in state.dv_model.satellites
                 if s.parent == "hub_candidate_business_entity"]
    assert twin_sats == ["sat_job_candidate_details"]


# --- Guard 4: without a twin, WP44's behaviour ----------------------------------------------


async def test_without_a_twin_everything_is_dropped_as_before() -> None:
    state = _state()
    state.retired_constructs = _retirements(with_twins=False)
    state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    assert "sat_job_candidate_details" not in {s.name for s in state.dv_model.satellites}
    assert "link_employee_assignment" not in {lk.name for lk in state.dv_model.links}
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_REPARENTED]
    assert len([f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]) >= 4
