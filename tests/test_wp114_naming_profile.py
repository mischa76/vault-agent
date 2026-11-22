"""WP114 — a `NamingProfile` in `rules/` beside the platform profile (C3, the naming half):
the staging prefix, the hash-key and hashdiff suffixes, the three technical columns and the
case of the technical names, carried by the run, persisted with the vault, adopted by an
extension. The default profile renders byte-identically. Committed red before the change.
Keyless."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.test_cli import _sqlite_stub_agents
from tests.test_target_platform import _bank_model, _typed_contracts
from tests.test_wp66_workbench_api import _project_with_inputs
from vault_agent import cli
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import build_staging
from vault_agent.cli import write_outputs
from vault_agent.existing_model import load_existing_naming
from vault_agent.extension_diff import _owner
from vault_agent.graph import build_graph
from vault_agent.rules.dv2_rules import stage_model_name
from vault_agent.rules.naming import DEFAULT_NAMING, NamingProfile
from vault_agent.state import VaultAgentState
from vault_agent.ui.app import create_app

LOWER = NamingProfile(
    staging_prefix="stage_", hashkey_suffix="_hk", hashdiff_suffix="_hashdiff",
    load_datetime="load_dts", record_source="rec_src", applied_dts="applied_dts",
    technical_case="lower",
)


# ── the default renders byte-identically ──────────────────────────────────────────────────
def test_the_default_profile_is_the_house_style_and_renders_byte_identically() -> None:
    assert NamingProfile() == DEFAULT_NAMING
    assert DEFAULT_NAMING.stage("hub_customer") == "stg_customer"
    assert stage_model_name("hub_customer") == "stg_customer"
    assert DEFAULT_NAMING.hashkey("CUSTOMER") == "CUSTOMER_HK"
    assert DEFAULT_NAMING.hashdiff("CUSTOMER_DETAILS") == "CUSTOMER_DETAILS_HASHDIFF"
    d = DEFAULT_NAMING
    technical = (d.load_datetime, d.record_source, d.applied_dts)
    assert technical == ("LOAD_DATETIME", "RECORD_SOURCE", "APPLIED_DTS")
    plain = build_staging(_bank_model(), [], contracts=_typed_contracts())
    explicit = build_staging(_bank_model(), [], contracts=_typed_contracts(),
                             naming=NamingProfile())
    assert plain.models == explicit.models and plain.scaffolding == explicit.scaffolding


# ── a lower-case profile through every renderer ───────────────────────────────────────────
async def test_a_lower_profile_names_the_vault_the_staging_and_the_contracts_consistently() -> None:
    state = VaultAgentState(dv_model=_bank_model(), naming=LOWER)
    state.artifacts.contracts = _typed_contracts()
    state = await CodeGeneratorAgent().run(state)
    hub = state.artifacts.dbt_models["hub_customer"]
    assert 'set src_pk = "customer_hk"' in hub and 'set src_ldts = "load_dts"' in hub
    assert 'set src_source = "rec_src"' in hub and 'set source_model = "stage_customer"' in hub
    sat = state.artifacts.dbt_models["sat_customer_details"]
    assert 'set src_hashdiff = "customer_details_hashdiff"' in sat
    assert "stage_customer" in state.artifacts.staging_models
    assert not any(name.startswith("stg_") for name in state.artifacts.staging_models)
    stage = state.artifacts.staging_models["stage_customer"]
    assert "customer_hk:" in stage and "customer_details_hashdiff:" in stage
    # the technical columns are the stage's expected source columns (its metadata, the README)
    meta = json.dumps(state.artifacts.automatedv_yaml["staging"]["stage_customer"])
    assert "load_dts" in meta and "rec_src" in meta and "LOAD_DATETIME" not in meta
    eff = next(sql for name, sql in state.artifacts.dbt_models.items() if name.endswith("_eff"))
    assert 'set src_eff = "applied_dts"' in eff
    readme = state.artifacts.scaffolding["README.md"]
    assert "`load_dts`" in readme and "`rec_src`" in readme
    project = yaml.safe_load(state.artifacts.scaffolding["dbt_project.yml"])
    seed = next(v for k, v in project["seeds"]["vault_project"].items() if k.startswith("raw_"))
    typed = set(seed["+column_types"])
    assert {"load_dts", "rec_src"} <= typed and "LOAD_DATETIME" not in typed
    assert state.artifacts.automatedv_yaml["staging"]["stage_customer"]["source_binding"]
    assert _owner("stage_customer", _bank_model(), naming=LOWER) == "hub_customer"


def test_the_contracts_dbt_model_follows_the_profile() -> None:
    from vault_agent.agents.data_contract import DataContractAgent
    from vault_agent.models.contract import ContractField, DataContract, FieldConstraints

    contract = DataContract(name="raw_customer", namespace="bank", dataAssetResourceName="x",
                            schema=[ContractField(name="customer id",
                                                  constraints=FieldConstraints(primaryKey=True))])
    rendered = DataContractAgent._render_dbt_tests("raw_customer", contract, naming=LOWER)
    assert "name: stage_raw_customer" in rendered
    assert "name: stg_raw_customer" in DataContractAgent._render_dbt_tests("raw_customer", contract)


# ── the profile travels and persists ──────────────────────────────────────────────────────
def test_the_state_carries_the_profile_and_the_output_persists_it(tmp_path: Path) -> None:
    state = VaultAgentState(dv_model=_bank_model(), naming=LOWER)
    assert VaultAgentState.model_validate_json(state.model_dump_json()).naming == LOWER
    write_outputs(VaultAgentState(dv_model=_bank_model()), tmp_path / "plain")
    assert not (tmp_path / "plain" / "metadata" / "naming.yml").exists()
    assert load_existing_naming(tmp_path / "plain") == DEFAULT_NAMING
    write_outputs(state, tmp_path / "lower")
    written = yaml.safe_load((tmp_path / "lower" / "metadata" / "naming.yml").read_text())
    assert written["staging_prefix"] == "stage_"
    assert load_existing_naming(tmp_path / "lower") == LOWER
    assert load_existing_naming(tmp_path / "lower" / "metadata" / "dv_model.yml") == LOWER


def test_the_cli_takes_a_profile_file_and_an_extension_adopts_its_vaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stubs = lambda *_a, **_k: _sqlite_stub_agents(block_signoff=False)  # noqa: E731
    monkeypatch.setattr(cli, "build_graph", lambda agents=None: build_graph(stubs()))
    doc = tmp_path / "req.md"
    doc.write_text("# Requirements\n\nA customer has a name.\n", encoding="utf-8")
    profile = tmp_path / "naming.yml"
    profile.write_text(yaml.safe_dump(LOWER.model_dump()), encoding="utf-8")
    first = tmp_path / "first"
    result = CliRunner().invoke(cli.app, [
        "run", str(doc), "--out", str(first), "--naming-profile", str(profile),
    ])
    assert result.exit_code == 0, result.output
    assert load_existing_naming(first) == LOWER
    # the stub agents build no model, and an extension needs one: a minimal vault stands in
    (first / "metadata" / "dv_model.yml").write_text(
        yaml.safe_dump(_bank_model().model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    second = tmp_path / "second"
    result = CliRunner().invoke(cli.app, [
        "run", str(doc), "--out", str(second), "--existing", str(first),
    ])
    assert result.exit_code == 0, result.output
    assert load_existing_naming(second) == LOWER  # adopted from the vault it extends
    other = tmp_path / "other.yml"
    other.write_text(yaml.safe_dump(NamingProfile(hashkey_suffix="_KEY").model_dump()),
                     encoding="utf-8")
    result = CliRunner().invoke(cli.app, [
        "run", str(doc), "--out", str(tmp_path / "third"), "--existing", str(first),
        "--naming-profile", str(other),
    ])
    assert result.exit_code == 1 and "naming" in result.output.lower()
    bad = tmp_path / "bad.yml"
    bad.write_text("technical_case: camel\n", encoding="utf-8")
    result = CliRunner().invoke(cli.app, [
        "run", str(doc), "--out", str(tmp_path / "fourth"), "--naming-profile", str(bad),
    ])
    assert result.exit_code == 1 and "technical_case" in result.output


# ── the workbench ─────────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    stubs = lambda *_a, **_k: _sqlite_stub_agents(block_signoff=True)  # noqa: E731
    monkeypatch.setattr(cli, "default_agents", stubs)
    monkeypatch.setattr(cli, "build_graph", lambda agents=None: build_graph(stubs()))
    return TestClient(create_app(tmp_path / "projects"))


def test_a_project_stores_a_naming_profile_and_its_runs_carry_it(client: TestClient) -> None:
    pid = _project_with_inputs(client)
    r = client.put(f"/api/projects/{pid}/settings", json={"naming": LOWER.model_dump()})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["naming"] == LOWER.model_dump()
    assert r.json()["effective"]["naming"] == LOWER.model_dump()
    assert client.put(f"/api/projects/{pid}/settings",
                      json={"naming": {"technical_case": "camel"}}).status_code == 422
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert run["naming"] == LOWER.model_dump()
    written = Path(run["out_dir"]) / "naming-profile.yml"
    assert yaml.safe_load(written.read_text()) == LOWER.model_dump()
    assert f"--naming-profile {written}" in run["cli_equivalents"][0]
    cleared = client.put(f"/api/projects/{pid}/settings", json={"naming": None})
    assert cleared.status_code == 200 and "naming" not in cleared.json()["settings"]
    plain = client.post(f"/api/projects/{pid}/runs?wait=true",
                        json={"requirements": "req.md", "schema": "schema.yml"}).json()
    assert plain["naming"] == DEFAULT_NAMING.model_dump()
    assert "--naming-profile" not in plain["cli_equivalents"][0]
