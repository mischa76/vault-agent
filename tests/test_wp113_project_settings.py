"""WP113 — project settings in the workbench (C3, the settings half): target platform, model
ids and an Anthropic-compatible base URL per project, applied to every run the project starts,
recorded in `run.json` and the CLI equivalents, carried by `pending.json` so `resume` and
`continue` build the same agents; the CLI's own flags for the same three; secrets stay in `.env`
and the API says only whether they are set. Committed red before the change. Keyless."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli, graph, llm
from vault_agent.config import LLMOptions
from vault_agent.graph import build_graph
from vault_agent.ui.app import create_app

OPTIONS = LLMOptions(primary_model="stub-primary", heavy_model="stub-heavy",
                     anthropic_base_url="http://proxy.local:8080")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # The pipeline on the stub agents whatever options a run pins; the wiring of real agents
    # from the options is the dedicated guard below.
    stubs = lambda *_a, **_k: _sqlite_stub_agents(block_signoff=True)  # noqa: E731
    monkeypatch.setattr(cli, "default_agents", stubs)
    monkeypatch.setattr(cli, "build_graph", lambda agents=None: build_graph(stubs()))
    return TestClient(create_app(tmp_path / "projects"))


# ── the settings themselves ───────────────────────────────────────────────────────────────
def test_a_new_project_has_no_settings_and_the_environment_shows(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    view = client.get(f"/api/projects/{pid}/settings").json()
    assert view["settings"] == {}
    assert view["effective"]["target_platform"] == "postgres"
    primary = view["effective"]["primary_model"]
    assert isinstance(primary, str) and primary
    assert isinstance(view["environment"]["anthropic_api_key_set"], bool)
    # never the value, only whether it is set: the one key-named field is the boolean
    assert [k for k in json.dumps(view).split('"') if "api_key" in k] == ["anthropic_api_key_set"]
    assert "sk-ant" not in json.dumps(view)
    assert view["environment"]["llm_provider"] in ("anthropic", "bedrock", "vertex")
    assert client.get("/api/projects/nope/settings").status_code == 404


def test_settings_are_stored_validated_and_read_back(client: TestClient, tmp_path: Path) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    body = {"target_platform": "databricks", "primary_model": "stub-primary",
            "heavy_model": "stub-heavy", "anthropic_base_url": "http://proxy.local:8080"}
    r = client.put(f"/api/projects/{pid}/settings", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["settings"] == body and r.json()["effective"]["target_platform"] == "databricks"
    assert json.loads((tmp_path / "projects" / pid / "settings.json").read_text()) == body
    assert client.get(f"/api/projects/{pid}/settings").json()["settings"] == body
    bad = client.put(f"/api/projects/{pid}/settings", json={"target_platform": "oracle"})
    assert bad.status_code == 422
    assert client.put(f"/api/projects/{pid}/settings",
                      json={"anthropic_base_url": "proxy.local"}).status_code == 422
    cleared = client.put(f"/api/projects/{pid}/settings", json={"primary_model": "  "})
    assert cleared.status_code == 200 and cleared.json()["settings"] == {}
    assert client.put("/api/projects/nope/settings", json={}).status_code == 404


# ── the run the project starts ────────────────────────────────────────────────────────────
def test_a_run_takes_the_projects_settings_and_records_them(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    client.put(f"/api/projects/{pid}/settings", json={
        "target_platform": "databricks", "primary_model": "stub-primary",
        "heavy_model": "stub-heavy", "anthropic_base_url": "http://proxy.local:8080",
    })
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["status"] == "paused"
    assert run["target_platform"] == "databricks"
    assert run["llm"] == {"primary_model": "stub-primary", "heavy_model": "stub-heavy",
                          "anthropic_base_url": "http://proxy.local:8080"}
    first = run["cli_equivalents"][0]
    for flag in ("--target-platform databricks", "--primary-model stub-primary",
                 "--heavy-model stub-heavy", "--anthropic-base-url http://proxy.local:8080"):
        assert flag in first, first
    pending = json.loads((Path(run["out_dir"]) / ".vault-agent" / "pending.json").read_text())
    assert pending["llm"] == run["llm"]
    # the body's own platform wins over the project's setting
    explicit = client.post(f"/api/projects/{pid}/runs?wait=true",
                           json={"requirements": "req.md", "target_platform": "postgres"}).json()
    assert explicit["target_platform"] == "postgres"


# ── the options reach the agents ──────────────────────────────────────────────────────────
def test_default_agents_hand_the_options_to_every_model_calling_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[tuple[str, str | None]] = []

    class _Caller:
        def __init__(self, model: str, *args: Any, base_url: str | None = None,
                     **kwargs: Any) -> None:
            built.append((model, base_url))

    monkeypatch.setattr(llm, "ForcedToolCaller", _Caller)
    graph.default_agents(OPTIONS)
    models = sorted(m for m, _ in built)
    assert models == ["stub-heavy"] + ["stub-primary"] * 5
    assert {u for _, u in built} == {"http://proxy.local:8080"}
    built.clear()
    graph.default_agents()  # the default path: each agent builds its helper lazily, from .env
    assert built == []


def test_the_client_carries_the_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    class _Client:
        def __init__(self, **kwargs: Any) -> None:
            captured.append(kwargs)

    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _Client)
    llm.ForcedToolCaller("m", base_url="http://proxy.local:8080")
    assert captured[-1]["base_url"] == "http://proxy.local:8080"
    llm.ForcedToolCaller("m")
    assert captured[-1].get("base_url") in (None, "")  # the SDK's default, ANTHROPIC_BASE_URL


# ── the CLI's flags and the pending pointer ──────────────────────────────────────────────
def test_write_pending_carries_the_options_and_read_pending_returns_them(tmp_path: Path) -> None:
    cli._write_pending(tmp_path, "t1", tmp_path / "req.md", llm=OPTIONS)
    pending = cli._read_pending(tmp_path)
    assert pending and pending["llm"] == OPTIONS.model_dump()
    cli._write_pending(tmp_path, "t1", tmp_path / "req.md")
    pending = cli._read_pending(tmp_path)
    assert pending and "llm" not in pending
    assert cli._pending_llm(pending) == LLMOptions()


def test_the_cli_run_records_its_flags_and_resume_rebuilds_the_same_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[LLMOptions | None] = []

    def fake_default_agents(options: LLMOptions | None = None) -> dict[str, object]:
        seen.append(options)
        return _sqlite_stub_agents(block_signoff=True)

    monkeypatch.setattr(cli, "default_agents", fake_default_agents)
    monkeypatch.setattr(cli, "build_graph", lambda agents=None: build_graph(agents))
    doc = tmp_path / "req.md"
    doc.write_text("# Requirements\n\nA customer has a name.\n", encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(cli.app, [
        "run", str(doc), "--out", str(out), "--primary-model", "stub-primary",
        "--heavy-model", "stub-heavy", "--anthropic-base-url", "http://proxy.local:8080",
    ])
    assert result.exit_code in (0, 2), result.output  # 2: paused at the checkpoint
    pending = cli._read_pending(out)
    assert pending and pending["llm"] == OPTIONS.model_dump()
    assert seen[-1] == OPTIONS
    result = CliRunner().invoke(cli.app, [
        "resume", "--out", str(out), "--owner", "customer=Jane Doe <jane@example.com>",
    ])
    assert result.exit_code == 0, result.output
    assert len(seen) == 2 and seen[-1] == OPTIONS  # the resume rebuilt the agents from the pointer
