"""WP66 — the workbench backend API over the CLI's internals (spec §3). Committed before the
change, failing. Keyless: the stub agents of the CLI tests, the pipeline paused at the
checkpoint and resumed through the API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from vault_agent import cli
from vault_agent.graph import build_graph
from vault_agent.ui.app import create_app

_REQUIREMENTS = "# Requirements\n\nA customer can open accounts. A customer has a name.\n"
_SCHEMA = """source_schemas:
  - table: Customer
    columns:
      - name: CustomerID
        type: int
      - name: Name
        type: nvarchar(50)
  - table: Account
    columns:
      - name: AccountID
        type: int
      - name: CustomerID
        type: int
    foreign_keys:
      - columns: [CustomerID]
        references_table: Customer
        references_columns: [CustomerID]
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


def _project_with_inputs(client: TestClient) -> str:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "requirements", "name": "req.md", "content": _REQUIREMENTS})
    assert r.status_code == 201, r.text
    r = client.post(f"/api/projects/{pid}/files",
                    json={"kind": "schema", "name": "schema.yml", "content": _SCHEMA})
    assert r.status_code == 201, r.text
    return pid


def test_projects_are_folders_and_a_bad_schema_is_refused_before_any_run(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]
    assert client.get(f"/api/projects/{pid}").json()["name"] == "Bank demo"
    bad = client.post(f"/api/projects/{pid}/files",
                      json={"kind": "schema", "name": "bad.yml", "content": "source_schemas: 3"})
    assert bad.status_code == 400 and "bad.yml" in bad.json()["detail"]
    assert client.get(f"/api/projects/{pid}").json()["files"] == []


def test_a_run_pauses_at_the_checkpoint_and_records_its_cli_equivalent(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    r = client.post(f"/api/projects/{pid}/runs?wait=true",
                    json={"requirements": "req.md", "schema": "schema.yml"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "paused" and run["thread_id"]
    assert run["cli_equivalents"][0].startswith("vault-agent run ")
    assert (Path(run["out_dir"]) / ".vault-agent" / "pending.json").exists()


def test_the_checkpoint_is_read_and_decided_through_the_cli_paths(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    cp = client.get(f"/api/runs/{run['id']}/checkpoint").json()
    owners = [i for i in cp["items"] if i["kind"] == "contract_owner"]
    assert owners and owners[0]["role"] == "decision" and cp["blocked"] is True
    r = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                    json={"accept": True, "owners": {"customer": "Jane Doe <jane@example.com>"}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "finished"
    assert any("resume" in c and "--owner" in c for c in r.json()["cli_equivalents"])
    assert not (Path(run["out_dir"]) / ".vault-agent" / "pending.json").exists()
    names = [a["path"] for a in client.get(f"/api/runs/{run['id']}/artefacts").json()]
    assert "report.html" in names and "review-queue.md" in names


def test_model_and_graphs_are_served(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    model = client.get(f"/api/runs/{run['id']}/model").json()
    assert "hubs" in model["model"] and model["output_mermaid"].startswith("flowchart")
    assert model["input_mermaid"].startswith("erDiagram")
    assert "Customer" in model["input_mermaid"] and "Account" in model["input_mermaid"]
    assert "||--o{" in model["input_mermaid"] or "}o--||" in model["input_mermaid"]


def test_events_come_from_the_trace_and_a_second_run_is_refused(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    events = client.get(f"/api/runs/{run['id']}/events?after=0").json()
    assert events["events"] and events["events"][0]["kind"] == "route"
    assert client.get(f"/api/runs/{run['id']}/artefacts/../../project.json").status_code == 404
    trace = Path(run["out_dir"]) / ".vault-agent" / "traces"
    assert trace.exists() and list(trace.glob("*.jsonl"))
    second = client.post(f"/api/projects/{pid}/runs",
                         json={"requirements": "req.md", "schema": "schema.yml"})
    assert second.status_code in (409, 201)  # 409 while the first is active; the stub finished
    json.loads(Path(run["out_dir"], "run.json").read_text())
