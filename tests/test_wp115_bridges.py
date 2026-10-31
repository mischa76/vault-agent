"""WP115 — bridges along link paths (C22, the open half of ADR-0016): a path the operator names
at start or a path proposed from the requirements' citations and ratified at sign-off, rendered
in the project's own SQL over the as-of spine, valid by the link's effectivity satellite where
one exists and by the load date otherwise. Committed red before the change. Keyless."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tests.test_agents.test_staging_generator import _bank_model
from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.agents.business_vault_generator import (
    bridge_model_name,
    parse_bridge_path,
    propose_bridge_paths,
)
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.graph import build_graph
from vault_agent.state import BusinessVaultOptions, DVModel, FlagKind, Link, VaultAgentState
from vault_agent.ui.app import create_app

PATH = "hub_customer,link_account_customer,hub_account"
BOUNDS: dict[str, Any] = {"as_of_start": date(2026, 1, 1), "as_of_end": date(2026, 3, 1)}


def _flags(state: VaultAgentState, kind: str) -> list[Any]:
    return [f for f in state.flags if f.kind == kind]


def _model() -> DVModel:
    """The bank shape plus the self-referencing transfer link (ADR-0009's role case)."""
    model = _bank_model()
    model.links.append(Link(name="link_transfer", description="a transfer between two accounts",
                            connected_hubs=["hub_account", "hub_account:counterparty"]))
    return model


# ── options and the path language ─────────────────────────────────────────────────────────
def test_a_bridge_needs_the_spines_bounds_like_a_pit() -> None:
    assert BusinessVaultOptions().bridges == []
    with pytest.raises(ValidationError):
        BusinessVaultOptions(bridges=[PATH])
    options = BusinessVaultOptions(bridges=[PATH], **BOUNDS)
    assert options.bridges == [PATH] and options.pit is False


def test_the_path_language_is_hubs_and_links_alternating_with_an_optional_role() -> None:
    model = _model()
    steps = parse_bridge_path(PATH, model)
    assert [s.construct for s in steps] == ["hub_customer", "link_account_customer", "hub_account"]
    assert bridge_model_name(steps) == "bridge_customer_account"
    roled = parse_bridge_path("hub_account,link_transfer,hub_account:counterparty", model)
    assert roled[-1].role == "counterparty" and bridge_model_name(roled) == "bridge_account_account"
    for bad in ("hub_customer", "hub_customer,hub_account",
                "hub_customer,link_transfer,hub_account",
                "hub_customer,link_account_customer,hub_branch",
                "link_account_customer,hub_account,x"):
        with pytest.raises(ValueError):
            parse_bridge_path(bad, model)


# ── rendering ─────────────────────────────────────────────────────────────────────────────
async def test_a_named_bridge_is_rendered_over_the_spine_with_the_links_effectivity() -> None:
    state = VaultAgentState(dv_model=_bank_model(),
                            business_vault=BusinessVaultOptions(bridges=[PATH], **BOUNDS))
    state = await CodeGeneratorAgent().run(state)
    models = state.artifacts.business_vault_models
    assert "as_of_dates" in models and "bridge_customer_account" in models
    sql = models["bridge_customer_account"]
    assert "ref('as_of_dates')" in sql and "ref('hub_customer')" in sql
    assert "ref('link_account_customer')" in sql and "ref('sat_account_customer_eff')" in sql
    assert "EFFECTIVE_FROM" in sql and "EFFECTIVE_TO" in sql and "AS_OF_DATE" in sql
    assert "CUSTOMER_HK" in sql and "ACCOUNT_HK" in sql and "LINK_ACCOUNT_CUSTOMER_HK" in sql
    meta = state.artifacts.automatedv_yaml["bridge"]["bridge_customer_account"]
    assert meta["path"] == PATH and meta["as_of_dates_table"] == "as_of_dates"
    assert meta["steps"][1]["validity"] == "effectivity_satellite"
    [flag] = _flags(state, FlagKind.BRIDGE_GENERATED)
    assert flag.asset == "bridge_customer_account"
    assert "pit_" not in " ".join(models)  # a bridge alone asks for no PIT


async def test_a_role_step_names_the_role_column_and_falls_back_to_the_load_date() -> None:
    path = "hub_account,link_transfer,hub_account:counterparty"
    state = VaultAgentState(dv_model=_model(),
                            business_vault=BusinessVaultOptions(bridges=[path], **BOUNDS))
    state = await CodeGeneratorAgent().run(state)
    sql = state.artifacts.business_vault_models["bridge_account_account"]
    assert "COUNTERPARTY_ACCOUNT_HK" in sql and "LOAD_DATETIME <= " in sql
    meta = state.artifacts.automatedv_yaml["bridge"]["bridge_account_account"]
    assert meta["steps"][1]["validity"] == "load_date"


async def test_an_unknown_path_is_a_generation_gap_not_a_crash() -> None:
    options = BusinessVaultOptions(bridges=["hub_customer,link_nope,hub_account"], **BOUNDS)
    state = VaultAgentState(dv_model=_bank_model(), business_vault=options)
    state = await CodeGeneratorAgent().run(state)
    assert "bridge" not in " ".join(state.artifacts.business_vault_models)
    [gap] = [f for f in _flags(state, FlagKind.GENERATION_GAP) if "bridge" in f.message]
    assert "link_nope" in gap.message


# ── proposals from the requirements' citations, ratified at sign-off ──────────────────────
def _cited_model() -> DVModel:
    model = _model().model_dump()
    for hub in model["hubs"]:
        hub["requirement_ids"] = ["REQ-001"]
    for link in model["links"]:
        link["requirement_ids"] = ["REQ-007"]  # both links cite the same requirement
    return DVModel.model_validate(model)


def test_two_links_citing_one_requirement_and_sharing_a_hub_propose_a_path() -> None:
    proposals = propose_bridge_paths(_cited_model())
    paths = {p.path for p in proposals}
    long = "hub_customer,link_account_customer,hub_account,link_transfer,hub_account"
    assert long + ":counterparty" in paths and long in paths
    assert len(proposals) == 2 and all(p.requirement_ids == ["REQ-007"] for p in proposals)
    assert propose_bridge_paths(_model()) == []  # nothing cited together: nothing proposed


async def test_proposals_are_decisions_only_when_the_business_vault_is_on() -> None:
    off = await CodeGeneratorAgent().run(VaultAgentState(dv_model=_cited_model()))
    assert _flags(off, FlagKind.BRIDGE_PROPOSED) == [] and off.bridge_proposals == []
    on = await CodeGeneratorAgent().run(VaultAgentState(
        dv_model=_cited_model(), business_vault=BusinessVaultOptions(pit=True, **BOUNDS)))
    proposed = _flags(on, FlagKind.BRIDGE_PROPOSED)
    assert proposed
    assert [f.asset for f in proposed] == [p.path for p in on.bridge_proposals]
    assert all(p.ratification_status == "proposed" for p in on.bridge_proposals)
    assert "--bridge" in proposed[0].message


async def test_a_ratified_proposal_is_rendered_and_a_declined_one_is_not() -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(
        dv_model=_cited_model(), business_vault=BusinessVaultOptions(pit=True, **BOUNDS)))
    first, second = state.bridge_proposals[0].path, state.bridge_proposals[1].path
    apply_human_decision(state, {"accept": True, "bridges": {first: True, second: False}})
    by_path = {p.path: p.ratification_status for p in state.bridge_proposals}
    assert by_path[first] == "accepted" and by_path[second] == "overridden"
    name = bridge_model_name(parse_bridge_path(first, state.dv_model))
    assert name in state.artifacts.business_vault_models
    assert name in state.artifacts.automatedv_yaml["bridge"]
    assert _flags(state, FlagKind.BRIDGE_PROPOSED) == []
    assert [f.asset for f in _flags(state, FlagKind.BRIDGE_GENERATED)] == [name]


def test_the_cli_decision_carries_the_bridges() -> None:
    decision = cli._build_decision([], True, bridges={PATH: True, "x,y,z": False})
    assert decision["bridges"] == {PATH: True, "x,y,z": False}


# ── the workbench ─────────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    stubs = lambda *_a, **_k: _sqlite_stub_agents(block_signoff=True)  # noqa: E731
    monkeypatch.setattr(cli, "default_agents", stubs)
    monkeypatch.setattr(cli, "build_graph", lambda agents=None: build_graph(stubs()))
    return TestClient(create_app(tmp_path / "projects"))


def test_a_run_records_named_bridges_and_a_decision_carries_them(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true", json={
        "requirements": "req.md", "schema": "schema.yml", "bridges": [PATH],
        "as_of_start": "2026-01-01", "as_of_end": "2026-03-01",
    }).json()
    assert run["status"] == "paused", run
    assert run["business_vault"]["bridges"] == [PATH]
    assert f"--bridge {PATH}" in run["cli_equivalents"][0]
    checkpoint = client.get(f"/api/runs/{run['id']}/checkpoint").json()
    assert checkpoint["bridges"] == []  # the stub builds no model, so nothing is proposed
    r = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                    json={"accept": True, "owners": {"customer": "Jane Doe <jane@example.com>"},
                          "bridges": {PATH: True, "a,b,c": False}})
    assert r.status_code == 200, r.text
    last = r.json()["cli_equivalents"][-1]
    assert f"--bridge {PATH}" in last and "--no-bridge a,b,c" in last
