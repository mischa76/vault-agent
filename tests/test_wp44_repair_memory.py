"""WP44 — repair memory: a hub the collision remedy retired does not come back (spec §3).

Committed before the change, failing. The fixture ``attempt3_cart_slice.json`` is cut verbatim
from llm_call 107 of the 2026-09-17 chain (step 5, modelling attempt 3): the cart constructs the
modeler re-emitted after attempt 2 had dropped ``hub_shopping_cart_item`` as told.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from tests.test_collision_remedy_guard import CANDIDATES, _business_entity, _vendor, _vendor_be
from vault_agent import llm
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    DVModel,
    FlagKind,
    RetiredConstruct,
    VaultAgentState,
)

_SLICE = Path(__file__).parent / "fixtures" / "wp44" / "attempt3_cart_slice.json"


def _slice_payload() -> dict:
    """The attempt-3 cart constructs plus the one hub they reference from the vault
    (``hub_product`` existed in step 5's existing model; here it is emitted greenfield so the
    product link is a legal link and not a dangling one)."""
    data = json.loads(_SLICE.read_text(encoding="utf-8"))
    payload = {k: data[k] for k in ("hubs", "links", "satellites")}
    payload["hubs"] = payload["hubs"] + [
        {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
         "description": "A product."}
    ]
    return payload


def _retired_cart_item() -> RetiredConstruct:
    return RetiredConstruct(
        name="hub_shopping_cart_item", kind="hub", code="E_HUB_HK_COLLISION", attempt=1
    )


# --- Guard 1: the validator records the retirement from the typed remedy ------------------


async def test_validator_records_the_remedys_drop_as_a_retirement() -> None:
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_business_entity(), _vendor(), _vendor_be()]),
        business_keys=CANDIDATES,
        modeling_attempts=1,
    )
    await ValidatorAgent().run(state)

    [issue] = [i for i in state.validation_report.issues if i.code == "E_HUB_HK_COLLISION"]
    assert issue.retires == ["hub_vendor_business_entity"]  # typed, not parsed from text
    assert [(r.name, r.kind, r.code, r.attempt) for r in state.retired_constructs] == [
        ("hub_vendor_business_entity", "hub", "E_HUB_HK_COLLISION", 1)
    ]


async def test_an_inherited_pair_retires_nothing() -> None:
    existing = DVModel(hubs=[_vendor(), _vendor_be()])
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_vendor(), _vendor_be()]),
        existing_model=existing,
        business_keys=CANDIDATES,
    )
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == "E_HUB_HK_COLLISION"]
    assert issue.retires == []
    assert state.retired_constructs == []


async def test_a_retirement_is_recorded_once_across_attempts() -> None:
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_business_entity(), _vendor(), _vendor_be()]),
        business_keys=CANDIDATES,
        modeling_attempts=1,
    )
    await ValidatorAgent().run(state)
    state.modeling_attempts = 2
    await ValidatorAgent().run(state)
    assert [r.name for r in state.retired_constructs] == ["hub_vendor_business_entity"]


# --- Guard 2: the modeler refuses the return, deterministically, with telemetry ------------


async def test_modeler_drops_a_retired_hub_its_links_and_its_satellite() -> None:
    stub = StubExtractor(_slice_payload())
    state = _state()
    state.retired_constructs = [_retired_cart_item()]
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        await Dv2ModelerAgent(extractor=stub).run(state)
    finally:
        llm.set_trace_recorder(None)

    model = state.dv_model
    assert [h.name for h in model.hubs] == ["hub_shopping_cart", "hub_product"]
    assert model.links == []  # both links named the retired hub
    assert model.satellites == []  # its satellite lost its parent

    reemitted = [f for f in state.flags if f.kind == FlagKind.RETIRED_REEMITTED]
    orphans = [f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]
    assert [f.asset for f in reemitted] == ["hub_shopping_cart_item"]
    assert sorted(f.asset for f in orphans) == [
        "link_shopping_cart_item_cart",
        "link_shopping_cart_item_product",
        "sat_shopping_cart_item_detail",
    ]
    # The orphaned satellite's payload is named: that is what the human must place.
    [sat_flag] = [f for f in orphans if f.asset == "sat_shopping_cart_item_detail"]
    assert "Quantity" in sat_flag.message and "DateCreated" in sat_flag.message

    backstops = [e for e in events if e.kind == "backstop"]
    assert [e.backstop_id for e in backstops] == ["retired_reemitted"]
    assert backstops[0].detail["retired"] == ["hub_shopping_cart_item"]
    assert sorted(backstops[0].detail["orphaned"]) == sorted(f.asset for f in orphans)

    # Guard 2, last clause: the retry payload names the retirement, typed.
    payload = json.loads(stub.calls[0][1])
    assert payload["retired_constructs"] == [
        {"name": "hub_shopping_cart_item", "kind": "hub", "code": "E_HUB_HK_COLLISION"}
    ]


# --- Guard 3: the repaired model passes the collision gate --------------------------------


async def test_the_repaired_model_raises_no_collision() -> None:
    stub = StubExtractor(_slice_payload())
    state = _state()
    state.retired_constructs = [_retired_cart_item()]
    await Dv2ModelerAgent(extractor=stub).run(state)
    await ValidatorAgent().run(state)
    assert not any(i.code == "E_HUB_HK_COLLISION" for i in state.validation_report.issues)


# --- Guard 4: inert when nothing is retired -----------------------------------------------


async def test_without_a_retirement_the_slice_passes_through_unchanged() -> None:
    stub = StubExtractor(_slice_payload())
    state = _state()
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        await Dv2ModelerAgent(extractor=stub).run(state)
    finally:
        llm.set_trace_recorder(None)

    assert sorted(h.name for h in state.dv_model.hubs) == [
        "hub_product", "hub_shopping_cart", "hub_shopping_cart_item"
    ]
    assert len(state.dv_model.links) == 2
    assert [s.name for s in state.dv_model.satellites] == ["sat_shopping_cart_item_detail"]
    assert not any(
        f.kind in (FlagKind.RETIRED_REEMITTED, FlagKind.RETIRED_ORPHAN) for f in state.flags
    )
    assert not any(e.kind == "backstop" and e.backstop_id == "retired_reemitted" for e in events)
    assert "retired_constructs" not in json.loads(stub.calls[0][1])
