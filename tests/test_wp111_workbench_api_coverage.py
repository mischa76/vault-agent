"""WP111 — the workbench tested through its API for every action that hands a path to the
filesystem or a subprocess, every error branch, the console's commands; and a coverage floor
for `vault_agent.ui` the CI enforces (C19). Keyless, on the CLI tests' stub agents."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.ui import project_check
from vault_agent.ui.app import create_app

ROOT = Path(__file__).resolve().parents[1]
UI_COVERAGE_FLOOR = 85  # percent of `vault_agent.ui` lines, measured by the whole suite in CI


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


@pytest.fixture
def finishing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=False))
    )
    return TestClient(create_app(tmp_path / "projects"))


def _paused(client: TestClient) -> dict[str, object]:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["status"] == "paused", run
    return run


def _finished(client: TestClient) -> dict[str, object]:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["status"] == "finished", run
    return run


# ── projects and files: names become paths ────────────────────────────────────────────────
def test_a_project_name_without_a_slug_and_a_duplicate_are_refused(client: TestClient) -> None:
    assert client.post("/api/projects", json={"name": "!!!"}).status_code == 400
    assert client.post("/api/projects", json={"name": "Bank demo"}).status_code == 201
    dup = client.post("/api/projects", json={"name": "bank  DEMO"})
    assert dup.status_code == 400 and "already exists" in dup.json()["detail"]
    assert client.get("/api/projects/nope").status_code == 404
    r = client.post("/api/projects/nope/files",
                    json={"kind": "requirements", "name": "r.md", "content": "x"})
    assert r.status_code == 404


@pytest.mark.parametrize("name", ["../escape.md", "sub/dir.md", "", "."])
def test_a_file_name_that_is_not_a_plain_name_never_reaches_the_disk(
    client: TestClient, tmp_path: Path, name: str
) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "requirements", "name": name, "content": "x"})
    assert r.status_code == 400, r.text
    assert not (tmp_path / "projects" / "escape.md").exists()
    assert sorted(p.name for p in (tmp_path / "projects" / pid / "inputs").iterdir()) == []


def test_a_wrong_suffix_and_an_empty_schema_are_refused_and_leave_no_file(
    client: TestClient, tmp_path: Path
) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "schema", "name": "schema.md", "content": "source_schemas: []"})
    assert r.status_code == 400 and "must be one of" in r.json()["detail"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "schema", "name": "empty.yml", "content": "source_schemas: []"})
    assert r.status_code == 400 and "declares no tables" in r.json()["detail"]
    assert not (tmp_path / "projects" / pid / "inputs" / "empty.yml").exists()
    assert client.get(f"/api/projects/{pid}").json()["files"] == []


# ── runs: inputs and predecessors are paths ───────────────────────────────────────────────
def test_a_run_on_a_missing_input_or_predecessor_is_a_404_and_a_bad_grain_a_422(
    client: TestClient,
) -> None:
    pid = _project_with_inputs(client)
    missing = client.post(f"/api/projects/{pid}/runs", json={"requirements": "nope.md"})
    assert missing.status_code == 404
    assert client.post("/api/projects/nope/runs", json={"requirements": "req.md"}).status_code == 404
    r = client.post(f"/api/projects/{pid}/runs", json={
        "requirements": "req.md", "schema": "schema.yml", "existing_run": "ghost",
    })
    assert r.status_code == 404, r.text
    r = client.post(f"/api/projects/{pid}/runs",
                    json={"requirements": "req.md", "pit": True, "as_of_grain": "fortnight"})
    assert r.status_code == 422, r.text


def test_every_run_route_answers_404_for_an_unknown_run(client: TestClient) -> None:
    gets = ["", "/events", "/checkpoint", "/artefacts", "/artefacts/report.html", "/project",
            "/model", "/report"]
    for suffix in gets:
        assert client.get(f"/api/runs/ghost{suffix}").status_code == 404, suffix
    posts = [("/checkpoint", {"accept": True}), ("/cancel", None), ("/continue", None),
             ("/parse", None), ("/console", {"text": "status"})]
    for suffix, body in posts:
        r = client.post(f"/api/runs/ghost{suffix}", json=body)
        assert r.status_code == 404, (suffix, r.text)


def test_events_page_past_the_end_and_the_artefacts_are_served_within_the_run(
    finishing: TestClient,
) -> None:
    run = _finished(finishing)
    rid = str(run["id"])
    events = finishing.get(f"/api/runs/{rid}/events?after=100000").json()
    assert events["events"] == [] and events["next"] == 100000 and events["status"] == "finished"
    listed = finishing.get(f"/api/runs/{rid}/artefacts").json()
    nested = next(a["path"] for a in listed if "/" in a["path"])
    assert finishing.get(f"/api/runs/{rid}/artefacts/{nested}").status_code == 200
    top = next(a["path"] for a in listed if "/" not in a["path"])
    assert finishing.get(f"/api/runs/{rid}/artefacts/{top}").status_code == 200
    assert finishing.get(f"/api/runs/{rid}/artefacts/missing.txt").status_code == 404
    # the checkpoint directory is not listed, but a named file under the run is still the run's
    assert ".vault-agent/state.json" not in {a["path"] for a in listed}
    assert finishing.get(f"/api/runs/{rid}/artefacts/.vault-agent/state.json").status_code == 200
    report = finishing.get(f"/api/runs/{rid}/report")
    assert report.status_code == 200 and "<html" in report.text.lower()


def test_a_finished_run_refuses_a_decision_a_cancel_and_a_continue(finishing: TestClient) -> None:
    """The codes as the API answers them today (pinned, not designed here): a decision or a
    continue on a run that is not paused or interrupted is a 400 (`ProjectError`, the run's
    status in the detail); a cancel of a run that is not running is a 409 (`RunConflictError`)."""
    run = _finished(finishing)
    rid = str(run["id"])
    decided = finishing.post(f"/api/runs/{rid}/checkpoint", json={"accept": True})
    assert decided.status_code == 400 and "finished" in decided.json()["detail"]
    cancelled = finishing.post(f"/api/runs/{rid}/cancel")
    assert cancelled.status_code == 409 and "nothing to cancel" in cancelled.json()["detail"]
    continued = finishing.post(f"/api/runs/{rid}/continue")
    assert continued.status_code == 400 and "not interrupted" in continued.json()["detail"]


def test_a_decision_that_both_accepts_and_discards_discards(client: TestClient) -> None:
    """Pinned as found (WP111): `discard` wins over `accept` in one body, the run is discarded
    and its CLI equivalent says `--discard`. Recorded in the log as an observation, not changed."""
    run = _paused(client)
    r = client.post(f"/api/runs/{run['id']}/checkpoint", json={"accept": True, "discard": True})
    assert r.status_code == 200 and r.json()["status"] == "discarded"
    assert r.json()["cli_equivalents"][-1].endswith("--discard")


# ── the console's grammar, every branch once ──────────────────────────────────────────────
COMMANDS = [
    "help", "?", "", "status", "items", "items decisions", "items disclosures", "explain 1",
    "explain 999", "explain W_HUB_NO_SAT", "explain E_DUP_HUB", "explain owner_placeholder",
    "explain customer", "gate E_DUP_NAME", "gates", "flags", "steering", "steering nope", "cli",
    "why hub_customer", "why nothing_here", "show hub_customer", "show nothing_here",
    "what if accept", "what if discard", "hub_customer", "E_DUP_HUB", "source_binding",
    "customer", "gibberish token",
]


@pytest.mark.parametrize("text", COMMANDS)
def test_every_console_command_answers_and_changes_nothing(client: TestClient, text: str) -> None:
    run = _paused(client)
    rid = str(run["id"])
    r = client.post(f"/api/runs/{rid}/console", json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] and body["kind"]
    assert client.get(f"/api/runs/{rid}").json()["status"] == "paused"


def test_the_console_names_what_it_does_not_know(client: TestClient) -> None:
    run = _paused(client)
    rid = str(run["id"])
    ask = lambda t: client.post(f"/api/runs/{rid}/console", json={"text": t}).json()  # noqa: E731
    assert ask("explain 999")["kind"] == "unknown"
    shown = ask("show nothing_here")
    assert shown["kind"] == "unknown" and "Hubs:" in shown["text"]
    assert ask("why nothing_here")["kind"] == "unknown"
    assert ask("gibberish token")["kind"] == "unknown"
    assert "fire" in ask("explain W_HUB_NO_SAT")["text"]
    assert ask("explain owner_placeholder")["text"].startswith("owner_placeholder:")
    assert ask("items disclosures")["text"]


# ── the project check's runner and the dbt probe ─────────────────────────────────────────
def test_the_default_runner_is_a_captured_subprocess_and_dbt_is_probed_from_the_install() -> None:
    done = project_check.run_command(["python3", "-c", "print('ok')"])
    assert done.returncode == 0 and done.stdout.strip() == "ok"
    available = project_check.dbt_available()
    assert available is None or set(available) == {"version", "adapter"}


# ── the floor the CI enforces ─────────────────────────────────────────────────────────────
def test_the_ci_measures_the_workbench_package_against_the_floor() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    fail_under = project["tool"]["coverage"]["report"]["fail_under"]
    assert fail_under >= UI_COVERAGE_FLOOR
    for workflow in ("ci.yml", "release.yml"):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if re.search(r"uv run pytest", ln)]
        assert lines and all("--cov=vault_agent.ui" in ln for ln in lines), workflow


# ── the console's construct, item and what-if branches on a constructed state ─────────────
def test_the_console_shows_links_satellites_items_and_the_what_if_variants() -> None:
    from tests.test_wp68_console import _state
    from vault_agent.ui.console import Console, answer

    state = _state()
    console = Console(state, None)
    link = state.dv_model.links[0].name
    sat = state.dv_model.satellites[0].name
    assert "participations" in answer(state, None, f"show {link}").text
    assert "parent:" in answer(state, None, f"show {sat}").text
    for n, item in enumerate(console.queue.items, 1):
        text = answer(state, None, f"explain {n}").text
        assert f"item {n}:" in text and item.kind in text
        if item.asset:
            assert item.asset in answer(state, None, f"explain {item.asset}").text
    assert "one_hub_per_key:" in answer(state, None, "steering one_hub_per_key").text
    assert answer(state, None, "steering nope").kind == "unknown"
    assert "No run.json" in answer(state, None, "cli").text
    meta = {"id": "r", "status": "paused", "out_dir": "/tmp/r",
            "cli_equivalents": ["vault-agent run x"]}
    assert "vault-agent run x" in answer(state, meta, "cli").text
    owner = answer(state, meta, "what if owner customer=Jane Doe <jane@example.com>")
    assert owner.command and "--owner" in owner.command
    resolve = answer(state, meta, "what if resolve customer=hub_x")
    assert resolve.command and "--resolve" in resolve.command
    assert answer(state, meta, "what if dance").kind == "unknown"
    assert "decisions" in answer(state, meta, "items decisions").text
