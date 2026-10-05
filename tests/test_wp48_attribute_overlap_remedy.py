"""WP48 — a remedy with memory for E_SAT_ATTR_OVERLAP (spec §3). Committed before the change,
failing. The fixture is the real step-2 shape of the cumulative chain `20261005T092147230544Z`:
``sat_employee_profile`` and ``sat_employee_demographics``, both from ``Employee``, both with
``MaritalStatus``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from vault_agent import llm
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import satellite_attribute_remedy
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    RetiredConstruct,
    Satellite,
    VaultAgentState,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "wp48" / "step2_employee_overlap.json"


def _payload() -> dict[str, Any]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {k: data[k] for k in ("hubs", "links", "satellites")}


def _model() -> DVModel:
    return DVModel.model_validate(_payload())


def _sat(name: str, attrs: list[str]) -> Satellite:
    return Satellite(name=name, parent="hub_employee", attributes=attrs,
                     source_table="Employee", description=name)


# --- Guard 1: the remedy's three rules ------------------------------------------------------


def test_first_by_name_keeps_the_attribute_among_new_satellites() -> None:
    profile, demographics = (s for s in _model().satellites)
    remedy = satellite_attribute_remedy([profile, demographics], "MaritalStatus", existing=None)
    assert remedy.keep == "sat_employee_demographics"
    assert remedy.drop == ["sat_employee_profile"]
    assert not remedy.inherited and "arbitrary" in remedy.text


def test_an_existing_satellite_always_keeps_it() -> None:
    profile, demographics = (s for s in _model().satellites)
    existing = DVModel(satellites=[profile])
    remedy = satellite_attribute_remedy([profile, demographics], "MaritalStatus", existing)
    assert remedy.keep == "sat_employee_profile" and remedy.drop == ["sat_employee_demographics"]
    assert "existing" in remedy.text


def test_an_inherited_pair_retires_nothing() -> None:
    profile, demographics = (s for s in _model().satellites)
    existing = DVModel(satellites=[profile, demographics])
    remedy = satellite_attribute_remedy([profile, demographics], "MaritalStatus", existing)
    assert remedy.inherited and remedy.keep is None and remedy.drop == []
    assert "do not re-emit" in remedy.text


# --- Guard 2: the validator carries it and records the retirement ---------------------------


async def test_the_gate_carries_the_remedy_and_retires_the_attribute() -> None:
    state = VaultAgentState(dv_model=_model(), modeling_attempts=1)
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == "E_SAT_ATTR_OVERLAP"]
    assert issue.remedy is not None and "sat_employee_demographics" in issue.remedy
    assert issue.retires_attributes == [["sat_employee_profile", "MaritalStatus"]]
    [retired] = state.retired_constructs
    assert (retired.kind, retired.name, retired.attribute) == (
        "attribute", "sat_employee_profile", "MaritalStatus"
    )


async def test_an_inherited_pair_records_no_retirement() -> None:
    model = _model()
    state = VaultAgentState(dv_model=model, existing_model=model.model_copy(deep=True))
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == "E_SAT_ATTR_OVERLAP"]
    assert issue.retires_attributes == [] and state.retired_constructs == []


# --- Guard 3: the memory drops the attribute from a re-emitted satellite --------------------


def _retired() -> RetiredConstruct:
    return RetiredConstruct(name="sat_employee_profile", kind="attribute",
                            code="E_SAT_ATTR_OVERLAP", attempt=1, attribute="MaritalStatus")


async def test_a_re_emitted_retired_attribute_is_dropped_and_the_model_is_green() -> None:
    state = _state()
    state.retired_constructs = [_retired()]
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    finally:
        llm.set_trace_recorder(None)

    by_name = {s.name: s for s in state.dv_model.satellites}
    assert by_name["sat_employee_profile"].attributes == ["JobTitle", "CurrentFlag",
                                                         "OrganizationLevel"]
    assert "MaritalStatus" in by_name["sat_employee_demographics"].attributes
    [flag] = [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]
    assert flag.asset == "sat_employee_profile" and "MaritalStatus" in flag.message
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]
    [event] = [e for e in events if e.kind == "backstop"]
    assert event.backstop_id == "retired_reemitted"
    assert event.detail["attributes_dropped"] == [["sat_employee_profile", "MaritalStatus"]]

    await ValidatorAgent().run(state)
    assert not [i for i in state.validation_report.issues if i.code == "E_SAT_ATTR_OVERLAP"]


# --- Guard 4: inert ---------------------------------------------------------------------------


async def test_without_a_retirement_the_shape_passes_through_unchanged() -> None:
    state = _state()
    state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    by_name = {s.name: s for s in state.dv_model.satellites}
    assert "MaritalStatus" in by_name["sat_employee_profile"].attributes
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]


async def test_a_satellite_re_emitted_without_the_attribute_raises_nothing() -> None:
    state = _state()
    state.retired_constructs = [_retired()]
    payload = _payload()
    for s in payload["satellites"]:
        if s["name"] == "sat_employee_profile":
            s["attributes"] = [a for a in s["attributes"] if a != "MaritalStatus"]
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]
    assert Hub  # the fixture's hub is validated through the model, not asserted here
