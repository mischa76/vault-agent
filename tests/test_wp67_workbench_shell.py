"""WP67 — the API additions the workbench shell needs (spec §3). Committed before the change,
failing. Keyless: the graph endpoint, the project's run history and the static serving."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.graph import NODES, build_graph, default_agents
from vault_agent.ui.app import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


def test_the_graph_endpoint_names_the_nodes_and_their_tool_names(client: TestClient) -> None:
    nodes = client.get("/api/graph").json()["nodes"]
    assert [n["id"] for n in nodes] == NODES
    agents = default_agents()
    for node in nodes:
        module = sys.modules[type(agents[node["id"]]).__module__]
        assert node["tool_name"] == getattr(module, "_TOOL_NAME", None)
    assert any(n["tool_name"] for n in nodes)  # the LLM agents are there


def test_a_project_carries_its_run_history_newest_first(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    assert client.get(f"/api/projects/{pid}").json()["runs"] == []
    first = client.post(f"/api/projects/{pid}/runs?wait=true",
                        json={"requirements": "req.md", "schema": "schema.yml"}).json()
    client.post(f"/api/runs/{first['id']}/checkpoint?wait=true", json={"discard": True})
    second = client.post(f"/api/projects/{pid}/runs?wait=true",
                         json={"requirements": "req.md", "schema": "schema.yml"}).json()
    runs = client.get(f"/api/projects/{pid}").json()["runs"]
    assert [r["id"] for r in runs] == [second["id"], first["id"]]
    assert runs[0]["status"] == "paused" and runs[1]["status"] == "discarded"
    assert set(runs[0]) >= {"id", "status", "started", "finished"}


def test_the_bundle_is_served_with_a_client_route_fallback(tmp_path: Path) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>wb</title>", encoding="utf-8")
    (static / "assets" / "x.js").write_text("console.log(1)", encoding="utf-8")
    client = TestClient(create_app(tmp_path / "projects", static=static))
    assert client.get("/").text.startswith("<!doctype html>")
    assert client.get("/p/bank/run/x").text.startswith("<!doctype html>")
    assert client.get("/assets/x.js").text == "console.log(1)"
    assert client.get("/api/projects").json() == []
    assert client.get("/api/nothing").status_code == 404


def test_without_a_bundle_the_root_names_the_build_command(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "projects", static=tmp_path / "missing"))
    r = client.get("/")
    assert r.status_code == 200 and "npm run build" in r.text


def test_the_contract_owner_decision_names_its_contract_as_the_asset(client: TestClient) -> None:
    """The Review perspective offers an owner input per contract on `asset`, never on the text."""
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    items = client.get(f"/api/runs/{run['id']}/checkpoint").json()["items"]
    owners = [i for i in items if i["kind"] == "contract_owner"]
    assert owners and all(i["asset"] for i in owners)
    assert owners[0]["asset"] == "customer"
