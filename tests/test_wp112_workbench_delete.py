"""WP112 — deleting in the workbench (C2): input files, runs and projects, through the API, with
the three rules the candidate named — a file a run has read is kept, a run another run extends is
kept while referenced, a running or paused run goes through cancel or discard first. Committed red
before the change. Keyless, on the CLI tests' stub agents."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.ui.app import create_app


def _slow_stub_agents() -> dict[str, object]:
    agents = _sqlite_stub_agents(block_signoff=True)
    modeler = agents["dv2_modeler"]
    inner = modeler.run  # type: ignore[attr-defined]

    async def slow(state: Any) -> Any:
        await asyncio.sleep(3)
        return await inner(state)

    modeler.run = slow  # type: ignore[attr-defined]
    return agents


@pytest.fixture
def pausing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


@pytest.fixture
def slow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(_slow_stub_agents()))
    return TestClient(create_app(tmp_path / "projects"))


def _run(client: TestClient, pid: str, **extra: Any) -> dict[str, Any]:
    body = {"requirements": "req.md", "schema": "schema.yml", **extra}
    r = client.post(f"/api/projects/{pid}/runs?wait=true", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


# ── input files ───────────────────────────────────────────────────────────────────────────
def test_an_unused_input_is_deleted_a_read_one_is_kept(finishing: TestClient, tmp_path: Path) -> None:
    pid = _project_with_inputs(finishing)
    r = finishing.post(f"/api/projects/{pid}/files",
                       json={"kind": "requirements", "name": "spare.md", "content": "# spare"})
    assert r.status_code == 201
    run = _run(finishing, pid)
    gone = finishing.delete(f"/api/projects/{pid}/files/spare.md")
    assert gone.status_code == 200 and gone.json()["deleted"] == "spare.md"
    assert not (tmp_path / "projects" / pid / "inputs" / "spare.md").exists()
    assert "spare.md" not in {f["name"] for f in finishing.get(f"/api/projects/{pid}").json()["files"]}
    kept = finishing.delete(f"/api/projects/{pid}/files/req.md")
    assert kept.status_code == 409 and run["id"] in kept.json()["detail"]
    assert (tmp_path / "projects" / pid / "inputs" / "req.md").exists()
    kept = finishing.delete(f"/api/projects/{pid}/files/schema.yml")
    assert kept.status_code == 409
    assert finishing.delete(f"/api/projects/{pid}/files/nope.md").status_code == 404
    assert finishing.delete(f"/api/projects/{pid}/files/..%2Fproject.json").status_code in (400, 404)
    assert (tmp_path / "projects" / pid / "project.json").exists()
    assert finishing.delete("/api/projects/nope/files/req.md").status_code == 404


# ── runs ──────────────────────────────────────────────────────────────────────────────────
def test_a_finished_run_is_deleted_whole_and_forgotten(finishing: TestClient, tmp_path: Path) -> None:
    pid = _project_with_inputs(finishing)
    first, second = _run(finishing, pid), _run(finishing, pid)
    before = _tree(tmp_path / "projects")
    out_dir = Path(first["out_dir"])
    assert out_dir.is_dir()
    r = finishing.delete(f"/api/runs/{first['id']}")
    assert r.status_code == 200 and r.json()["deleted"] == first["id"]
    assert not out_dir.exists()
    assert finishing.get(f"/api/runs/{first['id']}").status_code == 404
    assert finishing.post(f"/api/runs/{first['id']}/console", json={"text": "status"}).status_code == 404
    assert [x["id"] for x in finishing.get(f"/api/projects/{pid}").json()["runs"]] == [second["id"]]
    removed = before - _tree(tmp_path / "projects")
    assert removed and all(p.startswith(str(out_dir.relative_to(tmp_path / "projects"))) for p in removed)
    assert finishing.delete("/api/runs/ghost").status_code == 404


def test_a_paused_run_goes_through_discard_first(pausing: TestClient) -> None:
    pid = _project_with_inputs(pausing)
    run = _run(pausing, pid)
    assert run["status"] == "paused"
    refused = pausing.delete(f"/api/runs/{run['id']}")
    assert refused.status_code == 409 and "discard" in refused.json()["detail"]
    assert pausing.post(f"/api/runs/{run['id']}/checkpoint", json={"discard": True}).status_code == 200
    assert pausing.delete(f"/api/runs/{run['id']}").status_code == 200


def test_a_running_run_goes_through_cancel_first(slow: TestClient) -> None:
    pid = _project_with_inputs(slow)
    r = slow.post(f"/api/projects/{pid}/runs", json={"requirements": "req.md", "schema": "schema.yml"})
    run = r.json()
    assert run["status"] == "running"
    refused = slow.delete(f"/api/runs/{run['id']}")
    assert refused.status_code == 409 and "cancel" in refused.json()["detail"]
    assert slow.post(f"/api/runs/{run['id']}/cancel").json()["status"] == "interrupted"
    assert slow.delete(f"/api/runs/{run['id']}").status_code == 200


def test_a_run_another_run_extends_is_kept_while_referenced(finishing: TestClient) -> None:
    pid = _project_with_inputs(finishing)
    base = _run(finishing, pid)
    extension = _run(finishing, pid, existing_run=base["id"])
    refused = finishing.delete(f"/api/runs/{base['id']}")
    assert refused.status_code == 409 and extension["id"] in refused.json()["detail"]
    assert finishing.delete(f"/api/runs/{extension['id']}").status_code == 200
    assert finishing.delete(f"/api/runs/{base['id']}").status_code == 200


# ── projects ──────────────────────────────────────────────────────────────────────────────
def test_a_project_is_deleted_whole_once_its_runs_are_at_rest(pausing: TestClient, tmp_path: Path) -> None:
    pid = _project_with_inputs(pausing)
    other = pausing.post("/api/projects", json={"name": "Other"}).json()["id"]
    run = _run(pausing, pid)
    refused = pausing.delete(f"/api/projects/{pid}")
    assert refused.status_code == 409 and run["id"] in refused.json()["detail"]
    assert pausing.post(f"/api/runs/{run['id']}/checkpoint", json={"discard": True}).status_code == 200
    r = pausing.delete(f"/api/projects/{pid}")
    assert r.status_code == 200 and r.json()["deleted"] == pid and r.json()["runs"] == 1
    assert not (tmp_path / "projects" / pid).exists()
    assert pausing.get(f"/api/projects/{pid}").status_code == 404
    assert pausing.get(f"/api/runs/{run['id']}").status_code == 404
    assert [p["id"] for p in pausing.get("/api/projects").json()] == [other]
    assert (tmp_path / "projects" / other / "project.json").exists()
    assert pausing.delete("/api/projects/nope").status_code == 404


def test_a_project_whose_run_another_projects_run_extends_is_kept(finishing: TestClient) -> None:
    pid = _project_with_inputs(finishing)
    base = _run(finishing, pid)
    other = finishing.post("/api/projects", json={"name": "Other"}).json()["id"]
    for kind, name, content in (("requirements", "req.md", "# r\n\nA store."),):
        assert finishing.post(f"/api/projects/{other}/files",
                              json={"kind": kind, "name": name, "content": content}).status_code == 201
    r = finishing.post(f"/api/projects/{other}/runs?wait=true",
                       json={"requirements": "req.md", "existing_run": base["id"]})
    assert r.status_code == 201, r.text
    extension = r.json()
    refused = finishing.delete(f"/api/projects/{pid}")
    assert refused.status_code == 409 and extension["id"] in refused.json()["detail"]
    assert finishing.delete(f"/api/projects/{other}").status_code == 200
    assert finishing.delete(f"/api/projects/{pid}").status_code == 200
