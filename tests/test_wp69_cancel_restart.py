"""WP69 — cancellation and restart robustness of the workbench backend (spec §3). Committed
before the change, failing. Keyless, on the CLI tests' stub agents."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _REQUIREMENTS
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.ui.app import create_app


def _slow_stub_agents() -> dict[str, object]:
    """The stub agents with a modeler that takes a while — a window to cancel in."""
    agents = _sqlite_stub_agents(block_signoff=True)
    modeler = agents["dv2_modeler"]
    inner = modeler.run  # type: ignore[attr-defined]

    async def slow(state: Any) -> Any:
        await asyncio.sleep(3)
        return await inner(state)

    modeler.run = slow  # type: ignore[attr-defined]
    return agents


@pytest.fixture
def slow_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(_slow_stub_agents()))


@pytest.fixture
def fast_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )


def _project(client: TestClient) -> str:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "requirements", "name": "req.md", "content": _REQUIREMENTS})
    assert r.status_code == 201, r.text
    return pid


async def test_run_pipeline_takes_the_thread_id(tmp_path: Path, fast_graph: None) -> None:
    doc = tmp_path / "req.md"
    doc.write_text(_REQUIREMENTS, encoding="utf-8")
    out = tmp_path / "out"
    _state, _paused, thread = await cli._run_pipeline(doc, out, thread_id="feedfacefeedface")
    assert thread == "feedfacefeedface"
    assert (out / ".vault-agent" / "traces" / "feedfacefeedface.jsonl").exists()


def test_a_running_run_is_cancelled_into_an_interrupted_thread_and_continued(
    tmp_path: Path, slow_graph: None
) -> None:
    with TestClient(create_app(tmp_path / "projects")) as client:
        pid = _project(client)
        run = client.post(f"/api/projects/{pid}/runs", json={"requirements": "req.md"}).json()
        assert run["status"] == "running" and run["thread_id"]
        time.sleep(1.0)  # past the first nodes, inside the slow modeler
        r = client.post(f"/api/runs/{run['id']}/cancel")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "interrupted"
        pending = json.loads(
            (Path(run["out_dir"]) / ".vault-agent" / "pending.json").read_text(encoding="utf-8")
        )
        assert pending["phase"] == "crashed" and pending["thread_id"] == run["thread_id"]
        assert r.json()["cli_equivalents"][-1].startswith("vault-agent resume --out ")
        again = client.post(f"/api/runs/{run['id']}/cancel")
        assert again.status_code == 409
        cont = client.post(f"/api/runs/{run['id']}/continue?wait=true")
        assert cont.status_code == 200, cont.text
        assert cont.json()["status"] == "paused"
        done = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                           json={"accept": True, "owners": {"customer": "Jane <j@example.com>"}})
        assert done.json()["status"] == "finished"


def test_a_finished_run_survives_a_restart(tmp_path: Path, fast_graph: None) -> None:
    root = tmp_path / "projects"
    with TestClient(create_app(root)) as client:
        pid = _project(client)
        run = client.post(f"/api/projects/{pid}/runs?wait=true",
                          json={"requirements": "req.md"}).json()
        client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                    json={"accept": True, "owners": {"customer": "Jane <j@example.com>"}})
        assert (Path(run["out_dir"]) / ".vault-agent" / "state.json").exists()
    with TestClient(create_app(root)) as other:  # a new process over the same root
        model = other.get(f"/api/runs/{run['id']}/model")
        assert model.status_code == 200 and "hubs" in model.json()["model"]
        console = other.post(f"/api/runs/{run['id']}/console", json={"text": "status"})
        assert console.json()["kind"] == "answer" and "finished" in console.json()["text"]


def test_startup_reconciles_runs_the_server_died_on(tmp_path: Path, fast_graph: None) -> None:
    root = tmp_path / "projects"
    with TestClient(create_app(root)) as client:
        pid = _project(client)
        run = client.post(f"/api/projects/{pid}/runs?wait=true",
                          json={"requirements": "req.md"}).json()
        assert run["status"] == "paused"
    out = Path(run["out_dir"])
    meta = json.loads((out / "run.json").read_text(encoding="utf-8"))
    (out / "run.json").write_text(json.dumps({**meta, "status": "running"}), encoding="utf-8")
    (out / ".vault-agent" / "pending.json").unlink()
    # a second, thread-less run the server died on before anything was checkpointed
    dead = out.parent / "dead"
    dead.mkdir()
    (dead / "run.json").write_text(json.dumps({
        **meta, "id": f"{pid}:dead", "status": "running", "thread_id": None, "out_dir": str(dead),
    }), encoding="utf-8")
    with TestClient(create_app(root)) as other:
        revived = other.get(f"/api/runs/{run['id']}").json()
        assert revived["status"] == "interrupted" and "server" in (revived["error"] or "")
        assert (out / ".vault-agent" / "pending.json").exists()
        assert other.get(f"/api/runs/{pid}:dead").json()["status"] == "failed"
        r = other.post(f"/api/runs/{run['id']}/checkpoint?wait=true", json={"discard": True})
        assert r.status_code == 200 and r.json()["status"] == "discarded"
