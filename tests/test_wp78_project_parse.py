"""WP78 — the workbench says whether a run's project resolves and parses (spec §3). Committed
before the change, failing. Keyless and without dbt: the subprocess runner is a fake."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _project_with_inputs
from tests.test_wp74_self_contained_project import STEP1, STEP2, _model1, _model2
from vault_agent import cli
from vault_agent.agents.staging_generator import build_staging
from vault_agent.graph import build_graph
from vault_agent.ui import project_check as pc
from vault_agent.ui.app import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=True))
    )
    return TestClient(create_app(tmp_path / "projects"))


def _write_project(out_dir: Path, carried: bool = True) -> None:
    result = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1 if carried else None)
    for name, sql in result.models.items():
        (out_dir / "models" / "staging").mkdir(parents=True, exist_ok=True)
        (out_dir / "models" / "staging" / f"{name}.sql").write_text(sql, encoding="utf-8")
    for rel, text in result.scaffolding.items():
        (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (out_dir / rel).write_text(text, encoding="utf-8")
    (out_dir / "metadata").mkdir(exist_ok=True)
    (out_dir / "metadata" / "automatedv.yml").write_text(
        json.dumps({"hubs": {}, "staging": result.metadata}), encoding="utf-8"
    )


# ── §3.1 the deterministic check ───────────────────────────────────────────────────────────
def test_project_check_counts_stages_unresolved_and_inferred(tmp_path: Path) -> None:
    _write_project(tmp_path)
    check = pc.project_check(tmp_path)
    assert check["staging_models"] == 5  # two hubs, one link, two satellites (the spec said 3)
    assert check["unresolved"] == []
    assert check["inferred"] == ["stg_account_customer"]
    degraded = tmp_path / "degraded"
    _write_project(degraded, carried=False)  # the satellite's bare `Customer`: dbt cannot ref it
    assert "stg_customer_details" in pc.project_check(degraded)["unresolved"]
    assert pc.project_check(tmp_path / "nowhere")["staging_models"] == 0


# ── §3.2 dbt parse through an injectable runner ────────────────────────────────────────────
class _Runner:
    def __init__(self, code: int, out: str = "") -> None:
        self.code, self.out, self.calls = code, out, []  # type: int, str, list[list[str]]

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.code, stdout=self.out, stderr="")


def test_dbt_parse_runs_deps_then_parse_with_a_throwaway_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(tmp_path)
    monkeypatch.setattr(pc, "dbt_available", lambda: {"version": "1.9.10", "adapter": "postgres"})
    runner = _Runner(0, "Performance info: …")
    result = pc.dbt_parse(tmp_path, runner=runner)
    assert result["status"] == "ok" and result["adapter"] == "postgres"
    assert [c[:2] for c in runner.calls] == [["dbt", "deps"], ["dbt", "parse"]]
    parse_cmd = runner.calls[1]
    profiles_dir = Path(parse_cmd[parse_cmd.index("--profiles-dir") + 1])
    profile = (profiles_dir / "profiles.yml").read_text(encoding="utf-8")
    assert "type: postgres" in profile and "vault_project" in profile
    assert result["errors"] == [] and result["seconds"] >= 0


def test_dbt_parse_reports_the_error_lines_and_unavailability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(tmp_path)
    (tmp_path / "dbt_packages").mkdir()  # deps already installed: no `dbt deps`
    monkeypatch.setattr(pc, "dbt_available", lambda: {"version": "1.9.10", "adapter": "postgres"})
    out = ("12:00:00  Running with dbt=1.9.10\n12:00:01  Encountered an error:\n"
           "Compilation Error\n  Model 'model.vault_project.stg_x' depends on a node named "
           "'raw_x' which was not found\n")
    runner = _Runner(2, out)
    result = pc.dbt_parse(tmp_path, runner=runner)
    assert result["status"] == "failed"
    assert [c[:2] for c in runner.calls] == [["dbt", "parse"]]
    assert any("raw_x" in line for line in result["errors"])
    monkeypatch.setattr(pc, "dbt_available", lambda: None)
    never = _Runner(0)
    assert pc.dbt_parse(tmp_path, runner=never)["status"] == "unavailable"
    assert never.calls == []


# ── §3.3 the API ───────────────────────────────────────────────────────────────────────────
def test_the_api_reports_the_project_and_persists_a_parse(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _project_with_inputs(client)
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    r = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true",
                    json={"accept": True, "owners": {"customer": "Jane Doe <jane@example.com>"}})
    assert r.json()["status"] == "finished"
    empty = client.get(f"/api/runs/{run['id']}/project").json()
    assert empty["staging_models"] == 0 and empty["parse"] is None  # stub agents write no models
    _write_project(Path(run["out_dir"]))  # the project a real run would have written
    check = client.get(f"/api/runs/{run['id']}/project").json()
    assert check["staging_models"] == 5 and check["inferred"] == ["stg_account_customer"]
    assert check["parse"] is None and "dbt" in check
    monkeypatch.setattr(pc, "dbt_available", lambda: {"version": "1.9.10", "adapter": "postgres"})
    monkeypatch.setattr(pc, "run_command", _Runner(0, "ok"))
    parsed = client.post(f"/api/runs/{run['id']}/parse").json()
    assert parsed["status"] == "ok"
    again = client.get(f"/api/runs/{run['id']}/project").json()
    assert again["parse"]["status"] == "ok"
    meta = json.loads((Path(run["out_dir"]) / "run.json").read_text(encoding="utf-8"))
    assert meta["parse"]["status"] == "ok"
    equivalents = client.get(f"/api/runs/{run['id']}").json()["cli_equivalents"]
    assert any("dbt parse" in c for c in equivalents)
