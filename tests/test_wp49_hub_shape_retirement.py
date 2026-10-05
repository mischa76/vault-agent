"""WP49 — the repair memory retires a hub by its shape (spec §3). Committed before the change,
failing. The fixture is step 5 attempt 3 of the third chain (`20261005T160357535338Z`): the
retired `hub_person_sales` (Customer, PersonID) came back as `hub_person_customer`.
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

_FIXTURE = Path(__file__).parent / "fixtures" / "wp49" / "attempt3_customer_slice.json"


def _payload() -> dict[str, Any]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {k: data[k] for k in ("hubs", "links", "satellites")}


def _retired_by_shape() -> RetiredConstruct:
    """What attempt 1's validator recorded: the dropped hub, with its shape."""
    return RetiredConstruct(
        name="hub_person_sales", kind="hub", code="E_HUB_HK_COLLISION", attempt=1,
        source_entity="Customer", key_columns=["PERSONID"],
    )


# --- Guard 1: the validator records the shape ------------------------------------------------


async def test_the_validator_records_a_retired_hubs_shape() -> None:
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_business_entity(), _vendor(), _vendor_be()]),
        business_keys=CANDIDATES,
        modeling_attempts=1,
    )
    await ValidatorAgent().run(state)
    [retired] = state.retired_constructs
    assert retired.name == "hub_vendor_business_entity"
    assert retired.source_entity == "Vendor" and retired.key_columns == ["BUSINESSENTITYID"]


# --- Guard 2: the renamed duplicate is dropped -----------------------------------------------


async def test_a_retired_hub_re_emitted_under_another_name_is_dropped() -> None:
    state = _state()
    state.retired_constructs = [_retired_by_shape()]
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    finally:
        llm.set_trace_recorder(None)

    names = {h.name for h in state.dv_model.hubs}
    assert "hub_person_customer" not in names and "hub_customer" in names
    assert "link_customer_person" not in {l.name for l in state.dv_model.links}
    assert {l.name for l in state.dv_model.links} >= {"link_customer_store", "link_customer_territory"}
    [flag] = [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]
    assert flag.asset == "hub_person_customer"
    assert "hub_person_sales" in flag.message and "Customer" in flag.message
    [event] = [e for e in events if e.kind == "backstop"]
    assert event.backstop_id == "retired_reemitted" and "hub_person_customer" in event.detail["retired"]

    await ValidatorAgent().run(state)
    assert not [i for i in state.validation_report.issues if i.code == "E_HUB_HK_COLLISION"]


# --- Guard 3: the modeler is told the shape ---------------------------------------------------


async def test_the_retry_payload_forbids_the_shape_not_only_the_name() -> None:
    stub = StubExtractor(_payload())
    state = _state()
    state.retired_constructs = [_retired_by_shape()]
    await Dv2ModelerAgent(extractor=stub).run(state)
    payload = json.loads(stub.calls[0][1])
    [entry] = payload["retired_constructs"]
    assert entry["name"] == "hub_person_sales"
    assert entry["source_entity"] == "Customer" and entry["key_columns"] == ["PERSONID"]


# --- Guard 4: shape means shape ---------------------------------------------------------------


async def test_another_key_on_the_same_entity_passes_and_an_old_record_still_drops_by_name() -> None:
    state = _state()
    state.retired_constructs = [_retired_by_shape()]
    payload = _payload()
    for h in payload["hubs"]:
        if h["name"] == "hub_person_customer":
            h["business_key"] = "rowguid"  # same entity, another key: a different hub
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    assert "hub_person_customer" in {h.name for h in state.dv_model.hubs}
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]

    state = _state()
    state.retired_constructs = [RetiredConstruct(
        name="hub_person_customer", kind="hub", code="E_HUB_HK_COLLISION", attempt=1,
    )]  # a record without shape (pre-WP49) still retires by name
    state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    assert "hub_person_customer" not in {h.name for h in state.dv_model.hubs}
