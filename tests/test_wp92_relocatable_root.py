"""WP92 — ADR-0015's consequences (spec §4): a project root that moves (P1–P3) and the local-only
binding pinned (P4). P1–P3 committed red before the change; P4 is a pin, green by construction.
Keyless, on the CLI tests' stub agents."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _REQUIREMENTS
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.ui.app import create_app

_DEMO_ROOT = Path(__file__).resolve().parents[1] / "demo" / "workbench-adventureworks"
_OWNERS = {"accept": True, "owners": {"customer": "Jane <j@example.com>"}}


@pytest.fixture
def fast_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )


def _paused_run(client: TestClient) -> tuple[str, dict[str, Any]]:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "requirements", "name": "req.md", "content": _REQUIREMENTS})
    assert r.status_code == 201, r.text
    run = client.post(f"/api/projects/{pid}/runs?wait=true", json={"requirements": "req.md"}).json()
    assert run["status"] == "paused", run
    return pid, run


def _under(path: str, root: Path) -> bool:
    return Path(path).resolve().is_relative_to(root.resolve())


# P1 — a paused run under root A; A moved to B; a new app over B finishes it.
def test_a_moved_root_keeps_its_paused_run_decidable(tmp_path: Path, fast_graph: None) -> None:
    root_a = tmp_path / "a" / "projects"
    with TestClient(create_app(root_a)) as client:
        pid, run = _paused_run(client)
    root_b = tmp_path / "b" / "elsewhere"
    shutil.move(str(root_a), str(root_b))
    assert not root_a.exists()
    with TestClient(create_app(root_b)) as other:
        runs = other.get(f"/api/projects/{pid}").json()["runs"]
        assert [r["id"] for r in runs] == [run["id"]]
        assert runs[0]["status"] == "paused"
        got = other.get(f"/api/runs/{run['id']}").json()
        assert got["status"] == "paused" and _under(got["out_dir"], root_b), got["out_dir"]
        checkpoint = other.get(f"/api/runs/{run['id']}/checkpoint")
        assert checkpoint.status_code == 200, checkpoint.text
        done = other.post(f"/api/runs/{run['id']}/checkpoint?wait=true", json=_OWNERS)
        assert done.status_code == 200, done.text
        assert done.json()["status"] == "finished"
        artefacts = other.get(f"/api/runs/{run['id']}/artefacts")
        assert artefacts.status_code == 200 and artefacts.json(), artefacts.text
        assert (root_b / pid / "runs" / run["id"].partition(":")[2] / "run.json").is_file()


# P2 — a root given relative to one working directory, the app restarted from another.
def test_a_relative_root_survives_a_changed_working_directory(
    tmp_path: Path, fast_graph: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.chdir(here)
    with TestClient(create_app(Path("wb"))) as client:
        _pid, run = _paused_run(client)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with TestClient(create_app(here / "wb")) as other:
        got = other.get(f"/api/runs/{run['id']}")
        assert got.status_code == 200, got.text
        assert _under(got.json()["out_dir"], here / "wb"), got.json()["out_dir"]
        artefacts = other.get(f"/api/runs/{run['id']}/artefacts")
        assert artefacts.status_code == 200 and artefacts.json(), artefacts.text
        assert other.get(f"/api/runs/{run['id']}/checkpoint").status_code == 200


# P3 — the shipped demo as evidence: opened from a directory that is not the repository root.
@pytest.mark.skipif(not _DEMO_ROOT.is_dir(), reason="the shipped demo is not checked out")
def test_the_shipped_demo_opens_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(_DEMO_ROOT)) as client:
        projects = client.get("/api/projects").json()
        assert [p["id"] for p in projects] == ["adventureworks"]
        runs = client.get("/api/projects/adventureworks").json()["runs"]
        assert len(runs) >= 2 and all(r["status"] == "finished" for r in runs)
        for summary in runs:
            run = client.get(f"/api/runs/{summary['id']}").json()
            assert _under(run["out_dir"], _DEMO_ROOT), run["out_dir"]
            artefacts = client.get(f"/api/runs/{run['id']}/artefacts")
            assert artefacts.status_code == 200, artefacts.text
            paths = {a["path"] for a in artefacts.json()}
            assert "run.json" in paths, sorted(paths)[:5]
            has_project = any(p.endswith("dbt_project.yml") for p in paths)
            assert has_project, sorted(paths)[:10]


# P4 — the local-only binding, pinned (ADR-0015 Option C: reachable from elsewhere is Option B).
def test_the_workbench_binds_to_loopback_and_has_no_host_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uvicorn

    captured: dict[str, Any] = {}

    def fake_run(app: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    runner = CliRunner()
    ok = runner.invoke(cli.app, ["ui", "--root", str(tmp_path / "wb"), "--port", "1"])
    assert ok.exit_code == 0, ok.output
    assert captured["host"] == "127.0.0.1" and captured["port"] == 1
    refused = runner.invoke(cli.app, ["ui", "--root", str(tmp_path / "wb"), "--host", "0.0.0.0"])
    assert refused.exit_code != 0
    assert "No such option" in refused.output or "no such option" in refused.output.lower()
