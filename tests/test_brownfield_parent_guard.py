"""Guard written FIRST, 2026-09-14: in brownfield mode the modeler's links and satellites that
attach to an EXISTING hub survive parsing.

`Dv2ModelerAgent._validate_model` accepted a link only if every hub it connects was in the
modeler's own output, and a satellite only if its parent was. In an extension run the delta
deliberately does not re-emit existing hubs, and the extension prompt section tells the modeler
to link to them "by its exact name" — so every such link was dropped before the merge. Replayed
on the recorded sales step of `20260913T230429748887Z`: 12 of 23 modeler links dropped, each
naming an existing hub as missing (`hub_person`, `hub_address`, `hub_product`, …), plus the
satellites hanging off them. WP38 needs satellites on an existing hub; they would fall the same way.

Pinned: with an existing vault, a hub or link of that vault is a known endpoint for the delta.
A reference to a hub in neither the delta nor the vault is still dropped, and greenfield is
unchanged.
"""
from __future__ import annotations

from tests.test_agents.test_dv2_modeler import StubExtractor, _state, _valid_payload
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.state import DVModel, FlagKind, Hub, Link, LinkHubRef


def _existing() -> DVModel:
    return DVModel(
        hubs=[Hub(name="hub_branch", business_key="branch code", source_entity="branch",
                  description="A bank branch.")],
        links=[Link(name="link_branch_region", description="old",
                    connected_hubs=[LinkHubRef(hub="hub_branch"), LinkHubRef(hub="hub_region")])],
    )


def _payload() -> dict:  # type: ignore[type-arg]
    payload = _valid_payload()
    payload["links"].append({
        "name": "link_account_branch", "connected_hubs": ["hub_account", "hub_branch"],
        "description": "The branch that holds an account.",
    })
    payload["satellites"].append({
        "name": "sat_branch_opening_hours", "parent": "hub_branch",
        "attributes": ["opening hours"], "description": "New branch payload from this source.",
    })
    payload["links"].append({
        "name": "link_account_ghost", "connected_hubs": ["hub_account", "hub_ghost"],
        "description": "A hub nobody has.",
    })
    return payload


async def test_links_and_satellites_on_an_existing_hub_survive_parsing() -> None:
    state = _state()
    state.existing_model = _existing()
    await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    links = {lk.name for lk in state.dv_model.links}
    sats = {s.name for s in state.dv_model.satellites}
    assert "link_account_branch" in links
    assert "sat_branch_opening_hours" in sats
    assert "link_account_ghost" not in links  # in neither the delta nor the vault
    dropped = [f.asset for f in state.flags if f.kind == FlagKind.DROPPED_RECORD]
    assert dropped == ["link_account_ghost"]


async def test_greenfield_still_drops_a_link_to_a_hub_it_did_not_emit() -> None:
    state = _state()
    await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)
    links = {lk.name for lk in state.dv_model.links}
    assert "link_account_branch" not in links and "link_account_ghost" not in links
