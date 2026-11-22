"""WP68 — the state-driven console (spec §3). Committed before the change, failing. Keyless."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.rules.catalogue import FLAGS, GATES
from vault_agent.state import (
    FlagKind,
    Hub,
    Link,
    PipelineFlag,
    Satellite,
    ValidationIssue,
    VaultAgentState,
)
from vault_agent.ui.app import create_app
from vault_agent.ui.console import answer

ROOT = Path(__file__).resolve().parents[1]


def test_the_catalogues_match_the_code_and_the_manual() -> None:
    source = (ROOT / "src/vault_agent/agents/validator.py").read_text(encoding="utf-8")
    assert set(GATES) == set(re.findall(r'"([EW]_[A-Z_]+)"', source))
    kinds = {v for k, v in vars(FlagKind).items() if k.isupper() and isinstance(v, str)}
    assert set(FLAGS) == kinds
    chapter = (ROOT / "docs/operations/08-validation-gates.md").read_text(encoding="utf-8")
    assert set(GATES) <= set(re.findall(r"^\| `([EW]_[A-Z_]+)`", chapter, re.M))
    assert all(GATES.values()) and all(FLAGS.values())


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


def _paused_run(client: TestClient) -> dict[str, object]:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["status"] == "paused"
    return run


def _ask(client: TestClient, run_id: str, text: str) -> dict[str, object]:
    r = client.post(f"/api/runs/{run_id}/console", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_console_explains_the_paused_run_and_changes_nothing(client: TestClient) -> None:
    run = _paused_run(client)
    rid = str(run["id"])
    items = _ask(client, rid, "items")
    assert items["kind"] == "answer"
    assert "1." in str(items["text"]) and "customer" in str(items["text"])
    explained = _ask(client, rid, "explain 1")
    text = str(explained["text"])
    assert "customer" in text and "contract_owner" in text
    assert "decision" in text and "--owner" in text
    assert any(ref["perspective"] == "review" for ref in explained["refs"])
    status = _ask(client, rid, "status")
    assert "paused" in str(status["text"]) and "attempt" in str(status["text"])
    what_if = _ask(client, rid, "what if accept")
    command = str(what_if["command"])
    assert command.startswith("vault-agent resume --out ") and command.endswith("--accept")
    assert (Path(str(run["out_dir"])) / ".vault-agent" / "pending.json").exists()
    assert client.get(f"/api/runs/{rid}").json()["status"] == "paused"
    gate = _ask(client, rid, "gate E_DUP_HUB")
    assert GATES["E_DUP_HUB"] in str(gate["text"])
    unknown = _ask(client, rid, "frobnicate the widgets")
    assert unknown["kind"] == "unknown" and "help" in str(unknown["text"])


def _state() -> VaultAgentState:
    state = VaultAgentState()
    state.dv_model.hubs.append(Hub(name="hub_x", business_key="x_id", source_entity="x",
                                   description="the x"))
    state.dv_model.hubs.append(Hub(name="hub_y", business_key="y_id", source_entity="y",
                                   description="the y"))
    state.dv_model.links.append(Link(name="link_x_y", connected_hubs=["hub_x", "hub_y"],
                                     description="x to y"))
    state.dv_model.satellites.append(Satellite(name="sat_x_details", parent="hub_x",
                                               attributes=["colour"], description="x payload"))
    state.validation_report.issues.append(ValidationIssue(
        severity="error", code="E_DUP_HUB", construct="hub_x",
        message="twice", remedy="keep hub_x, drop hub_x2", retires=["hub_x2"]))
    state.modeling_attempts = 2
    state.flags.append(PipelineFlag(agent="dv2_modeler", message="inferred",
                                    kind=FlagKind.RELATION_INFERRED, asset="hub_x"))
    return state


def test_show_why_steering_and_flags_on_a_constructed_state() -> None:
    state = _state()
    shown = answer(state, None, "show hub_x").text
    assert "x_id" in shown and "x" in shown and "sat_x_details" in shown and "link_x_y" in shown
    why = answer(state, None, "why hub_x").text
    assert "E_DUP_HUB" in why and "keep hub_x" in why and "hub_x2" in why and "attempt" in why
    assert FlagKind.RELATION_INFERRED in why
    steering = answer(state, None, "steering").text
    assert "one_hub_per_key" in steering and "canon" in steering
    flags = answer(state, None, "flags").text
    assert "relation_inferred" in flags and "1" in flags
    routed = answer(state, None, "hub_x")  # free text equal to a construct name
    assert "x_id" in routed.text


def test_a_run_without_state_in_this_session_answers_unavailable(client: TestClient) -> None:
    run = _paused_run(client)
    rid = str(run["id"])
    client.post(f"/api/runs/{rid}/checkpoint?wait=true",
                json={"accept": True, "owners": {"customer": "Jane Doe <jane@example.com>"}})
    # WP69 persists a finished run's state beside its trace; without that file a second app
    # over the same root has nothing to answer from (the guard's original shape, narrowed)
    (Path(str(run["out_dir"])) / ".vault-agent" / "state.json").unlink()
    other = TestClient(create_app(Path(str(run["out_dir"])).parents[2]))
    r = other.post(f"/api/runs/{rid}/console", json={"text": "status"})
    assert r.status_code == 200 and r.json()["kind"] == "unavailable"
