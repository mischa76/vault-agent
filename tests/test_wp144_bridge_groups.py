"""WP144 — a proposed bridge is one decision per link pair and shared hub (C53 option (a), spec
§4). The proposer's paths and what is stored per path do not change; the decisions do: one
`bridge_proposed` flag per group, the prompt asking once per group, the page's pending list
carrying the group. Committed red before the change; G4 is a pin. Keyless."""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from vault_agent import cli
from vault_agent.agents.business_vault_generator import bridge_group, propose_bridge_paths
from vault_agent.agents.code_generator import CodeGeneratorAgent, bridge_proposal_flags
from vault_agent.agents.orchestrator import apply_human_decision, assemble_review_queue
from vault_agent.existing_model import declined_bridge_paths
from vault_agent.state import (
    BusinessVaultOptions,
    DVModel,
    FlagKind,
    Hub,
    Link,
    LinkHubRef,
    VaultAgentState,
)
from vault_agent.ui.runs import _pending_bridges

BOUNDS: dict[str, Any] = {"as_of_start": date(2026, 1, 1), "as_of_end": date(2026, 3, 1)}
AB_C = "hub_branch,link_account_branch,hub_account,link_account_customer,hub_customer"
AB_T = "hub_branch,link_account_branch,hub_account,link_transfer,hub_account"
AB_T_ROLE = AB_T + ":counterparty"
AC_T = "hub_customer,link_account_customer,hub_account,link_transfer,hub_account"
AC_T_ROLE = AC_T + ":counterparty"
G_AB_C = "link_account_branch+link_account_customer@hub_account"
G_AB_T = "link_account_branch+link_transfer@hub_account"
G_AC_T = "link_account_customer+link_transfer@hub_account"


def _hub(name: str) -> Hub:
    base = name.removeprefix("hub_")
    return Hub(name=name, business_key=f"{base}_id", source_entity=base, description="",
               requirement_ids=["REQ-007"])


def _model() -> DVModel:
    """Three links citing one requirement around `hub_account`, one of them a self-link with a
    role: five paths in three link pairs."""
    return DVModel(
        hubs=[_hub("hub_customer"), _hub("hub_account"), _hub("hub_branch")],
        links=[
            Link(name="link_account_customer", connected_hubs=["hub_account", "hub_customer"],
                 description="", requirement_ids=["REQ-007"]),
            Link(name="link_account_branch", connected_hubs=["hub_account", "hub_branch"],
                 description="", requirement_ids=["REQ-007"]),
            Link(name="link_transfer", description="", requirement_ids=["REQ-007"],
                 connected_hubs=[LinkHubRef(hub="hub_account"),
                                 LinkHubRef(hub="hub_account", role="counterparty")]),
        ],
    )


def _bridge_flags(state: VaultAgentState) -> list[Any]:
    return [f for f in state.flags if f.kind == FlagKind.BRIDGE_PROPOSED]


def test_the_fixture_is_five_paths() -> None:
    assert [p.path for p in propose_bridge_paths(_model())] == [
        AB_C, AB_T, AB_T_ROLE, AC_T, AC_T_ROLE
    ]


# ── G1 the group ──────────────────────────────────────────────────────────────────────────
def test_g1_a_proposed_path_belongs_to_its_link_pair_and_shared_hub() -> None:
    assert bridge_group(AB_C) == G_AB_C
    assert bridge_group(AB_T) == bridge_group(AB_T_ROLE) == G_AB_T
    assert bridge_group("hub_x:a,link_one,hub_y:via,link_two,hub_z") == "link_one+link_two@hub_y"


def test_g1_a_path_of_another_shape_is_a_group_of_its_own() -> None:
    short = "hub_customer,link_account_customer,hub_account"
    long = AB_C + ",link_customer_region,hub_region"
    assert bridge_group(short) == short and bridge_group(long) == long


# ── G2 one flag per group with an unanswered path ─────────────────────────────────────────
def test_g2_three_groups_over_five_paths_are_three_decisions() -> None:
    proposals = propose_bridge_paths(_model())
    flags = bridge_proposal_flags(proposals)
    assert [f.asset for f in flags] == [G_AB_C, G_AB_T, G_AC_T]
    assert all(f.kind == FlagKind.BRIDGE_PROPOSED for f in flags)
    assert AB_T in flags[1].message and AB_T_ROLE in flags[1].message
    assert AC_T not in flags[1].message and "--bridge" in flags[1].message
    assert "link_account_branch" in flags[1].message and "hub_account" in flags[1].message


def test_g2_a_group_keeps_its_decision_while_a_path_is_unanswered() -> None:
    proposals = propose_bridge_paths(_model())
    by_path = {p.path: p for p in proposals}
    by_path[AB_T].ratification_status = "overridden"
    flags = {f.asset: f for f in bridge_proposal_flags(proposals)}
    assert set(flags) == {G_AB_C, G_AB_T, G_AC_T}
    assert AB_T_ROLE in flags[G_AB_T].message
    assert f'"{AB_T}"' not in flags[G_AB_T].message, "an answered path is no longer offered"
    by_path[AB_T_ROLE].ratification_status = "accepted"
    assert [f.asset for f in bridge_proposal_flags(proposals)] == [G_AB_C, G_AC_T]


# ── G3 the review queue counts groups ─────────────────────────────────────────────────────
async def test_g3_the_generator_stores_every_path_and_asks_per_group() -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(
        dv_model=_model(), business_vault=BusinessVaultOptions(pit=True, **BOUNDS)))
    assert len(state.bridge_proposals) == 5
    assert [f.asset for f in _bridge_flags(state)] == [G_AB_C, G_AB_T, G_AC_T]
    queue = assemble_review_queue(state)
    asked = [i for i in queue.items if i.role == "decision" and i.kind == "review_flag"
             and i.asset in {G_AB_C, G_AB_T, G_AC_T}]
    assert len(asked) == 3


# ── G4 (pin) answers stay per path ────────────────────────────────────────────────────────
async def test_g4_building_one_path_of_a_group_declines_its_sibling_at_accept() -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(
        dv_model=_model(), business_vault=BusinessVaultOptions(pit=True, **BOUNDS)))
    apply_human_decision(state, {"accept": True, "bridges": {AB_T_ROLE: True}})
    status = {p.path: p.ratification_status for p in state.bridge_proposals}
    assert status[AB_T_ROLE] == "accepted" and status[AB_T] == "overridden"
    assert _bridge_flags(state) == []
    assert declined_bridge_paths(state) == sorted([AB_C, AB_T, AC_T, AC_T_ROLE])


# ── G5 the page's pending list ────────────────────────────────────────────────────────────
def test_g5_the_pending_list_says_which_group_a_path_belongs_to() -> None:
    state = VaultAgentState(dv_model=_model(), bridge_proposals=propose_bridge_paths(_model()))
    pending = {entry["path"]: entry for entry in _pending_bridges(state)}
    assert list(pending) == [AB_C, AB_T, AB_T_ROLE, AC_T, AC_T_ROLE]
    assert (pending[AB_T_ROLE]["group"], pending[AB_T_ROLE]["links"], pending[AB_T_ROLE]["hub"]) == (
        G_AB_T, ["link_account_branch", "link_transfer"], "hub_account")
    state.bridge_proposals[1].ratification_status = "overridden"
    assert AB_T not in {entry["path"] for entry in _pending_bridges(state)}


# ── G6 the prompt asks once per group ─────────────────────────────────────────────────────
class _Scripted:
    def __init__(self, confirms: list[bool], texts: list[str]) -> None:
        self.confirms, self.texts = confirms, texts
        self.asked: list[str] = []

    def confirm(self, console: Any, message: str, *, default: bool = False) -> bool:
        self.asked.append(message)
        return self.confirms.pop(0)

    def text(self, console: Any, message: str) -> str:
        self.asked.append(message)
        return self.texts.pop(0)


def test_g6_the_prompt_asks_per_group_and_then_for_the_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    from rich.console import Console

    state = VaultAgentState(dv_model=_model(), bridge_proposals=propose_bridge_paths(_model()))
    scripted = _Scripted(confirms=[True, True, False], texts=["7", "2"])
    monkeypatch.setattr(cli, "_prompter", scripted)
    answers = cli._collect_bridge_decision(Console(file=io.StringIO()), state)
    assert answers == {AB_C: True, AB_T: False, AB_T_ROLE: True, AC_T: False, AC_T_ROLE: False}
    confirms = [m for m in scripted.asked if m.startswith("Build a bridge")]
    assert len(confirms) == 3 and "link_account_branch" in confirms[1]
    # one path: no question which; two paths: asked, and asked again after an answer out of range
    assert len([m for m in scripted.asked if m.startswith("Which path")]) == 2
