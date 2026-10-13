"""WP71 — the workbench shows and answers the resolution checkpoint (spec §3). Committed
before the change, failing. Keyless: the CLI tests' stub agents with a pending key license and
the real resolution checkpoint."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.agents.entity_resolver import ResolutionCheckpointAgent
from vault_agent.graph import build_graph
from vault_agent.state import KeyLicense, VaultAgentState
from vault_agent.ui.app import create_app

LICENSE_KEY = "Account.CustomerID"


def _agents_with_a_pending_license() -> dict[str, object]:
    agents = _sqlite_stub_agents(block_signoff=True)
    proposer = agents["link_proposer"]
    inner = proposer.run  # type: ignore[attr-defined]

    async def propose(state: VaultAgentState) -> Any:
        state.link_proposals.licenses.append(KeyLicense(
            source_table="Account", source_column="CustomerID",
            references_table="Customer", references_column="CustomerID",
            evidence=["Account.CustomerID → Customer.CustomerID (declared)"],
        ))
        return await inner(state)

    proposer.run = propose  # type: ignore[attr-defined]
    agents["resolution_checkpoint"] = ResolutionCheckpointAgent()  # the real pause
    return agents


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(_agents_with_a_pending_license()))
    return TestClient(create_app(tmp_path / "projects"))


@pytest.fixture
def plain_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


def test_the_first_pause_is_the_resolution_phase_with_the_license(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["status"] == "paused"
    cp = client.get(f"/api/runs/{run['id']}/checkpoint").json()
    assert cp["phase"] == "resolution"
    [license_] = cp["links"]
    assert license_["key"] == LICENSE_KEY and license_["kind"] == "license"
    assert "Customer" in license_["target"] and license_["note"] and license_["evidence"]
    assert cp["resolutions"] == [] and cp["answers"]  # the CLI's answer vocabulary


def test_declining_the_license_resumes_into_signoff_and_both_pauses_are_recorded(
    client: TestClient,
) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    r = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                    json={"links": {LICENSE_KEY: False}, "accept": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"
    assert r.json()["cli_equivalents"][-1].endswith(f"--no-link {LICENSE_KEY} --accept")
    cp = client.get(f"/api/runs/{run['id']}/checkpoint").json()
    assert cp["phase"] == "signoff" and cp["links"] == []
    assert any(i["kind"] == "contract_owner" for i in cp["items"])
    done = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                       json={"accept": True, "owners": {"customer": "Jane <j@example.com>"}})
    assert done.json()["status"] == "finished"
    meta = json.loads((Path(run["out_dir"]) / "run.json").read_text(encoding="utf-8"))
    assert [c["phase"] for c in meta["checkpoints"]] == ["resolution", "signoff"]
    assert meta["checkpoints"][0]["command"] == r.json()["cli_equivalents"][-1]


def test_the_plain_stub_pauses_at_signoff_only(plain_client: TestClient) -> None:
    pid = _project_with_inputs(plain_client)
    run = plain_client.post(f"/api/projects/{pid}/runs?wait=true",
                            json={"requirements": "req.md", "schema": "schema.yml"}).json()
    cp = plain_client.get(f"/api/runs/{run['id']}/checkpoint").json()
    assert cp["phase"] == "signoff" and cp["links"] == [] and cp["resolutions"] == []
