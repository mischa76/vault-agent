"""WP82 — bindings at sign-off: a stage's relation and its column aliases ratified in CLI and
workbench alike (spec §2–§3). Committed before the change, failing. Keyless throughout: the real
code generator over a hand-built model, the stub pipeline of the CLI tests under the API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from vault_agent import cli
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.graph import build_graph
from vault_agent.state import DVModel, FlagKind, SourceTable, VaultAgentState
from vault_agent.ui.app import create_app

# The owner's `raw_business_entity_store_sales_person` in miniature: the link's stage expects the
# sales person's key under the hub's name (BUSINESSENTITYID) while the relation carries it as
# SalesPersonID — WP73 refuses the offer, and only a hand view could say "that column, under this
# name" until now.
STORE = SourceTable.model_validate({
    "table": "StoreMaster", "schema": "Sales",
    "columns": [{"name": "StoreID", "type": "int"}, {"name": "SalesPersonID", "type": "int"},
                {"name": "Name", "type": "nvarchar(50)"}],
    "primary_key": ["StoreID"],
    "foreign_keys": [{"columns": ["SalesPersonID"], "references_table": "SalesPerson",
                      "references_columns": ["BusinessEntityID"]}],
})
SALES_PERSON = SourceTable.model_validate({
    "table": "SalesPerson", "schema": "Sales",
    "columns": [{"name": "BusinessEntityID", "type": "int"}, {"name": "TerritoryID", "type": "int"}],
    "primary_key": ["BusinessEntityID"],
})
# A hub stage no rule binds (`none`): the composite key lives in a table named otherwise.
ROUTING = SourceTable.model_validate({
    "table": "WorkOrderRouting", "schema": "Production",
    "columns": [{"name": "WorkOrderID", "type": "int"}, {"name": "OperationSequence", "type": "smallint"},
                {"name": "LocationID", "type": "smallint"}],
    "primary_key": ["WorkOrderID", "ProductID", "OperationSequence"],
})


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_store", "business_key": "StoreID", "source_entity": "store",
             "description": "x"},
            {"name": "hub_sales_person", "business_key": "BusinessEntityID",
             "source_entity": "SalesPerson", "description": "x"},
            {"name": "hub_work_order_operation", "business_key": "work order operation",
             "business_key_columns": ["WorkOrderID", "OperationSequence"],
             "source_entity": "work order operation", "description": "x"},
        ],
        "links": [{"name": "link_store_sales_person",
                   "connected_hubs": ["hub_store", "hub_sales_person"], "description": "x"}],
        "satellites": [],
    })


async def _generated() -> VaultAgentState:
    state = VaultAgentState(dv_model=_model(), source_schemas=[STORE, SALES_PERSON, ROUTING])
    return await CodeGeneratorAgent().run(state)


def _staging(state: VaultAgentState) -> dict[str, Any]:
    return state.artifacts.automatedv_yaml.get("staging") or {}


# ── the parser and its inverse ────────────────────────────────────────────────────────────


def test_parse_bind_plain_and_with_aliases() -> None:
    from vault_agent.bindings import StageBinding, format_bind, parse_bind

    assert parse_bind("stg_work_order_operation=WorkOrderRouting") == (
        "stg_work_order_operation", StageBinding(relation="WorkOrderRouting"),
    )
    stage, binding = parse_bind(
        "stg_store_sales_person=StoreMaster(BUSINESSENTITYID=SalesPersonID, STOREID = StoreID)"
    )
    assert stage == "stg_store_sales_person"
    assert binding == StageBinding(
        relation="StoreMaster", columns={"BUSINESSENTITYID": "SalesPersonID", "STOREID": "StoreID"}
    )
    assert parse_bind(format_bind(stage, binding)) == (stage, binding)
    for bad in ("stg_x", "=Rel", "stg_x=", "stg_x=Rel(BUSINESSENTITYID)", "stg_x=Rel(=a)"):
        with pytest.raises(ValueError, match="--bind"):
            parse_bind(bad)


# ── the check every path runs first ───────────────────────────────────────────────────────


async def test_check_names_the_stage_the_relation_and_the_missing_columns() -> None:
    from vault_agent.bindings import StageBinding, check_stage_bindings

    state = await _generated()
    assert _staging(state)["stg_store_sales_person"]["source_binding"] == "inferred"

    def errors(stage: str, relation: str, **columns: str) -> list[str]:
        return check_stage_bindings(
            state, {stage: StageBinding(relation=relation, columns=dict(columns))}
        )

    assert errors("stg_nope", "StoreMaster") and "stg_nope" in errors("stg_nope", "StoreMaster")[0]
    [undeclared] = errors("stg_store_sales_person", "Shop")
    assert "Shop" in undeclared
    [missing] = errors("stg_store_sales_person", "StoreMaster")
    assert "BUSINESSENTITYID" in missing and "StoreMaster" in missing
    [alias_target] = errors("stg_store_sales_person", "StoreMaster", BUSINESSENTITYID="SellerID")
    assert "SellerID" in alias_target
    assert errors("stg_store_sales_person", "StoreMaster", BUSINESSENTITYID="SalesPersonID") == []
    assert errors("stg_work_order_operation", "WorkOrderRouting") == []


# ── application: the stage binds, the alias is derived, the flag goes ─────────────────────


async def test_a_ratified_binding_with_an_alias_binds_the_refused_link_stage() -> None:
    state = await _generated()
    before = {f.asset for f in state.flags if f.kind == FlagKind.BINDING_REJECTED}
    assert "stg_store_sales_person" in before  # WP73's refusal is the starting point

    apply_human_decision(state, {"bindings": {
        "stg_store_sales_person": {"relation": "StoreMaster",
                                   "columns": {"BUSINESSENTITYID": "SalesPersonID"}},
    }})

    meta = _staging(state)["stg_store_sales_person"]
    assert meta["source_binding"] == "declared"
    assert list(meta["source_model"].values()) == ["StoreMaster"]
    assert meta["derived_columns"]["BUSINESSENTITYID"] == "SalesPersonID"
    assert meta["ratified_columns"] == {"BUSINESSENTITYID": "SalesPersonID"}
    assert "SalesPersonID" in state.artifacts.staging_models["stg_store_sales_person"]
    assert not [f for f in state.flags
                if f.kind in (FlagKind.BINDING_REJECTED, FlagKind.SOURCE_BINDING)
                and f.asset == "stg_store_sales_person"]
    assert state.ratified_bindings["stg_store_sales_person"].relation == "StoreMaster"


async def test_a_ratified_binding_binds_a_hub_stage_no_rule_could() -> None:
    state = await _generated()
    assert _staging(state)["stg_work_order_operation"]["source_binding"] == "inferred"
    apply_human_decision(
        state, {"bindings": {"stg_work_order_operation": {"relation": "WorkOrderRouting"}}}
    )
    meta = _staging(state)["stg_work_order_operation"]
    assert meta["source_binding"] == "declared"
    assert list(meta["source_model"].values()) == ["WorkOrderRouting"]
    assert "ratified_columns" not in meta  # no alias, nothing to record


async def test_an_invalid_binding_is_skipped_and_the_flag_stays() -> None:
    state = await _generated()
    apply_human_decision(state, {"bindings": {"stg_store_sales_person": {"relation": "Shop"}}})
    assert _staging(state)["stg_store_sales_person"]["source_binding"] == "inferred"
    assert not state.ratified_bindings


async def test_a_ratified_binding_overrides_a_rule_binding() -> None:
    """The decision is last: `stg_sales_person` binds to SalesPerson by name; the human says
    another declared relation that carries the key, and that one is read."""
    other = SourceTable.model_validate({
        "table": "SalesPersonQuotaHistory", "schema": "Sales",
        "columns": [{"name": "BusinessEntityID", "type": "int"}, {"name": "QuotaDate", "type": "datetime"}],
    })
    state = VaultAgentState(dv_model=_model(), source_schemas=[STORE, SALES_PERSON, ROUTING, other])
    state = await CodeGeneratorAgent().run(state)
    assert list(_staging(state)["stg_sales_person"]["source_model"].values()) == ["SalesPerson"]
    apply_human_decision(
        state, {"bindings": {"stg_sales_person": {"relation": "SalesPersonQuotaHistory"}}}
    )
    assert list(_staging(state)["stg_sales_person"]["source_model"].values()) == [
        "SalesPersonQuotaHistory"
    ]


# ── it travels: the aliases in the catalogue, applied by the next increment ───────────────


async def test_the_alias_travels_with_the_catalogue_to_the_next_increment(tmp_path: Path) -> None:
    from vault_agent.existing_model import (
        load_carried_aliases,
        load_carried_bindings,
        load_existing_catalogue,
    )

    state = await _generated()
    apply_human_decision(state, {"bindings": {
        "stg_store_sales_person": {"relation": "StoreMaster",
                                   "columns": {"BUSINESSENTITYID": "SalesPersonID"}},
    }})
    cli.write_outputs(state, tmp_path)
    catalogue = yaml.safe_load((tmp_path / "metadata" / "source_catalogue.yml").read_text())
    assert catalogue["stage_bindings"]["stg_store_sales_person"] == "StoreMaster"
    assert catalogue["stage_aliases"] == {
        "stg_store_sales_person": {"BUSINESSENTITYID": "SalesPersonID"}
    }
    assert load_carried_aliases(tmp_path) == catalogue["stage_aliases"]

    # The next increment: the same constructs exist already, the increment declares nothing of
    # Sales, and the stage must bind again — relation AND alias — from the catalogue alone.
    following = VaultAgentState(
        dv_model=_model(), existing_model=_model(), source_schemas=[],
        carried_schemas=load_existing_catalogue(tmp_path),
        carried_bindings=load_carried_bindings(tmp_path),
        carried_aliases=load_carried_aliases(tmp_path),
    )
    following = await CodeGeneratorAgent().run(following)
    meta = _staging(following)["stg_store_sales_person"]
    assert meta["source_binding"] == "declared"
    assert meta["derived_columns"]["BUSINESSENTITYID"] == "SalesPersonID"
    assert not [f for f in following.flags if f.kind == FlagKind.BINDING_REJECTED]


def test_a_catalogue_without_the_block_loads_as_before(tmp_path: Path) -> None:
    from vault_agent.existing_model import dump_source_catalogue, load_carried_aliases

    (tmp_path / "metadata").mkdir()
    (tmp_path / "metadata" / "source_catalogue.yml").write_text(
        dump_source_catalogue([STORE], {"stg_store": "StoreMaster"}), encoding="utf-8"
    )
    assert load_carried_aliases(tmp_path) == {}
    assert load_carried_aliases(tmp_path / "nowhere") == {}


# ── the CLI: a decision flag like the others, the prompt the same payload ─────────────────


def test_bind_is_a_decision_flag_and_build_decision_carries_it() -> None:
    from vault_agent.bindings import StageBinding

    assert cli._has_decision_flags(None, False, None, None, None, None, None, None, ["a=B"])
    assert not cli._has_decision_flags(None, False, None, None, None, None, None, None, None)
    decision = cli._build_decision(
        [], False, bindings={"stg_a": StageBinding(relation="B", columns={"X": "y"})}
    )
    assert decision["bindings"] == {"stg_a": {"relation": "B", "columns": {"X": "y"}}}
    assert json.dumps(decision)  # the checkpointer's payload stays plain JSON


class _Prompter:
    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.asked: list[str] = []

    def text(self, console: object, message: str) -> str:
        self.asked.append(message)
        return self._answers.pop(0) if self._answers else ""

    def confirm(self, console: object, message: str, *, default: bool = False) -> bool:
        return True


async def test_the_prompt_asks_for_each_pending_stage_and_yields_the_flags_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rich.console import Console

    from vault_agent.bindings import parse_bind

    state = await _generated()
    pending = {f.asset for f in state.flags
               if f.kind in (FlagKind.BINDING_REJECTED, FlagKind.SOURCE_BINDING)}
    scripted = _Prompter(["StoreMaster(BUSINESSENTITYID=SalesPersonID)", "Shop", "", ""])
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)

    answers = cli._collect_binding_decision(Console(), state)

    asked_for = {m.split("'")[1] for m in scripted.asked if m.startswith("Relation for stage")}
    assert asked_for == pending  # every inferred or refused stage, once each
    stage, binding = parse_bind("stg_store_sales_person=StoreMaster(BUSINESSENTITYID=SalesPersonID)")
    assert answers == {stage: binding}  # "Shop" was refused by the check and re-asked, then skipped
    assert any("Shop" in m for m in scripted.asked)  # the refusal was shown at the prompt


# ── the API: the same decision, validated first, recorded as `--bind` ─────────────────────

_REQUIREMENTS = "# Requirements\n\nA store is served by a sales person.\n"
_SCHEMA = yaml.safe_dump({"source_schemas": [
    STORE.model_dump(by_alias=True, exclude_none=True),
    SALES_PERSON.model_dump(by_alias=True, exclude_none=True),
    ROUTING.model_dump(by_alias=True, exclude_none=True),
]}, sort_keys=False)
_PROFILING = yaml.safe_dump({"tables": [{"table": "StoreMaster", "columns": [
    {"name": "StoreID", "uniqueness_ratio": 1.0, "null_ratio": 0.0, "distinct_count": 701},
]}]})


def _modelled_stub_agents() -> dict[str, object]:
    """The CLI tests' stubs, with a modeler that writes the store model and the REAL code
    generator — so the paused run has a refused link stage to bind."""
    from vault_agent.agents.base import BaseAgent

    agents = _sqlite_stub_agents(block_signoff=True)

    class _Modeler(BaseAgent):
        name = "dv2_modeler"

        async def run(self, state: VaultAgentState) -> VaultAgentState:
            state.dv_model = _model()
            return state

    agents["dv2_modeler"] = _Modeler()
    agents["code_generator"] = CodeGeneratorAgent()
    return agents


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(_modelled_stub_agents()))
    return TestClient(create_app(tmp_path / "projects"))


def _paused_run(client: TestClient, **start: Any) -> tuple[str, dict[str, Any]]:
    pid = client.post("/api/projects", json={"name": "Stores"}).json()["id"]
    for kind, name, content in (("requirements", "req.md", _REQUIREMENTS),
                                ("schema", "schema.yml", _SCHEMA),
                                ("profiling", "prof.yml", _PROFILING)):
        r = client.post(f"/api/projects/{pid}/files", json={"kind": kind, "name": name, "content": content})
        assert r.status_code == 201, r.text
    r = client.post(f"/api/projects/{pid}/runs?wait=true",
                    json={"requirements": "req.md", "schema": "schema.yml", **start})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "paused"
    return pid, run


def test_the_checkpoint_lists_the_pending_stages_and_a_binding_is_applied_and_recorded(
    client: TestClient,
) -> None:
    _pid, run = _paused_run(client)
    cp = client.get(f"/api/runs/{run['id']}/checkpoint").json()
    pending = {b["stage"]: b for b in cp["bindings"]}
    assert set(pending) >= {"stg_store_sales_person", "stg_work_order_operation"}
    store = pending["stg_store_sales_person"]
    assert store["reason"] == "rejected" and store["tried"] == "StoreMaster"
    assert "BUSINESSENTITYID" in store["expected_columns"]
    assert pending["stg_work_order_operation"]["reason"] == "none"

    r = client.post(f"/api/runs/{run['id']}/checkpoint?wait=true", json={
        "accept": True, "owners": {"customer": "jane@example.com"},
        "bindings": {
            "stg_store_sales_person": {"relation": "StoreMaster",
                                       "columns": {"BUSINESSENTITYID": "SalesPersonID"}},
            "stg_work_order_operation": {"relation": "WorkOrderRouting"},
        },
        "mappings": {"store": "StoreMaster.StoreID"},
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "finished"
    equivalent = r.json()["cli_equivalents"][-1]
    assert "--bind 'stg_store_sales_person=StoreMaster(BUSINESSENTITYID=SalesPersonID)'" in equivalent
    assert "--bind stg_work_order_operation=WorkOrderRouting" in equivalent
    assert "--map store=StoreMaster.StoreID" in equivalent
    meta = yaml.safe_load((Path(run["out_dir"]) / "metadata" / "automatedv.yml").read_text())
    assert meta["staging"]["stg_store_sales_person"]["source_binding"] == "declared"
    assert meta["staging"]["stg_work_order_operation"]["source_binding"] == "declared"


def test_a_binding_the_relation_cannot_carry_is_refused_with_400_before_anything_runs(
    client: TestClient,
) -> None:
    _pid, run = _paused_run(client)
    r = client.post(f"/api/runs/{run['id']}/checkpoint", json={
        "accept": True, "bindings": {"stg_store_sales_person": {"relation": "StoreMaster"}},
    })
    assert r.status_code == 400, r.text
    assert "BUSINESSENTITYID" in r.json()["detail"] and "StoreMaster" in r.json()["detail"]
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "paused"


def test_profiling_and_the_platform_start_a_run_through_the_api(client: TestClient) -> None:
    pid, run = _paused_run(client, profiling="prof.yml", target_platform="databricks")
    assert run["profiling"] == "prof.yml" and run["target_platform"] == "databricks"
    equivalent = run["cli_equivalents"][0]
    assert "--profiling" in equivalent and "prof.yml" in equivalent
    assert "--target-platform databricks" in equivalent
    meta = json.loads((Path(run["out_dir"]) / "run.json").read_text())
    assert meta["profiling"] == "prof.yml" and meta["target_platform"] == "databricks"
    summary = client.get(f"/api/projects/{pid}").json()["runs"][0]
    assert summary["profiling"] == "prof.yml" and summary["target_platform"] == "databricks"


def test_the_default_platform_leaves_the_equivalent_as_before(client: TestClient) -> None:
    _pid, run = _paused_run(client)
    assert run["target_platform"] == "postgres" and run["profiling"] is None
    assert "--target-platform" not in run["cli_equivalents"][0]
    assert "--profiling" not in run["cli_equivalents"][0]


def test_an_unknown_platform_is_refused(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Stores"}).json()["id"]
    client.post(f"/api/projects/{pid}/files",
                json={"kind": "requirements", "name": "req.md", "content": _REQUIREMENTS})
    r = client.post(f"/api/projects/{pid}/runs",
                    json={"requirements": "req.md", "target_platform": "oracle"})
    assert r.status_code == 422
