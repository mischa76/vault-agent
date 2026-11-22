"""WP122 (C53, option b) — bridge proposals: no path back to its start, and a declined path is not
proposed again in an extension. Committed before the change, failing. The cycle is the twenty-fifth
chain's Production shape (size and weight unit of measure on one product). Keyless."""
from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tests.test_wp115_bridges import BOUNDS, _cited_model
from vault_agent import cli
from vault_agent.agents.business_vault_generator import propose_bridge_paths
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.existing_model import load_declined_bridges
from vault_agent.state import BusinessVaultOptions, DVModel, FlagKind, VaultAgentState
from vault_agent.ui import runs

CYCLE = ("hub_product,link_product_size_unit_measure,hub_unit_measure:size,"
         "link_product_weight_unit_measure,hub_product")
ACROSS = ("hub_unit_measure:size,link_product_size_unit_measure,hub_product,"
          "link_product_weight_unit_measure,hub_unit_measure:weight")


def _unit_model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": "ProductID", "source_entity": "Product",
             "description": "p",
             "requirement_ids": ["REQ-092"]},
            {"name": "hub_unit_measure", "business_key": "UnitMeasureCode",
             "source_entity": "UnitMeasure", "description": "u",
             "requirement_ids": ["REQ-092"]},
        ],
        "links": [
            {"name": "link_product_size_unit_measure", "description": "size unit",
             "connected_hubs": ["hub_product", "hub_unit_measure:size"],
             "requirement_ids": ["REQ-092"]},
            {"name": "link_product_weight_unit_measure", "description": "weight unit",
             "connected_hubs": ["hub_product", "hub_unit_measure:weight"],
             "requirement_ids": ["REQ-092"]},
        ],
        "satellites": [],
    })


def _on(**extra: Any) -> VaultAgentState:
    return VaultAgentState(dv_model=_cited_model(),
                           business_vault=BusinessVaultOptions(pit=True, **BOUNDS), **extra)


# ── T1: a path back to its own start is not proposed; one between two roles is ─────────────
def test_a_path_back_to_its_start_is_not_proposed() -> None:
    paths = {p.path for p in propose_bridge_paths(_unit_model())}
    assert CYCLE not in paths
    assert ACROSS in paths


# ── T2: the proposer leaves out what it is told was declined ───────────────────────────────
def test_declined_paths_are_left_out() -> None:
    every = [p.path for p in propose_bridge_paths(_cited_model())]
    assert len(every) == 2
    rest = [p.path for p in propose_bridge_paths(_cited_model(), declined={every[0]})]
    assert rest == every[1:]


# ── T3: the code generator reads the state's carried declines ──────────────────────────────
async def test_the_generator_does_not_propose_a_carried_decline_again() -> None:
    first = await CodeGeneratorAgent().run(_on())
    declined = first.bridge_proposals[0].path
    again = await CodeGeneratorAgent().run(_on(declined_bridges=[declined]))
    assert declined not in {p.path for p in again.bridge_proposals}
    assert declined not in {f.asset for f in again.flags if f.kind == FlagKind.BRIDGE_PROPOSED}
    assert len(again.bridge_proposals) == len(first.bridge_proposals) - 1


# ── T4/T5: the output records the declines, the next run reads them ─────────────────────────
async def test_declines_are_written_beside_the_model_and_read_back(tmp_path: Path) -> None:
    state = await CodeGeneratorAgent().run(_on(declined_bridges=["hub_a,link_x,hub_b"]))
    first, second = state.bridge_proposals[0].path, state.bridge_proposals[1].path
    apply_human_decision(state, {"accept": True, "bridges": {first: True}})  # second unanswered
    cli.write_outputs(state, tmp_path)
    document = yaml.safe_load((tmp_path / "metadata" / "bridge_decisions.yml").read_text())
    assert document == {"declined": sorted(["hub_a,link_x,hub_b", second])}
    assert load_declined_bridges(tmp_path) == sorted(["hub_a,link_x,hub_b", second])
    assert load_declined_bridges(tmp_path / "metadata" / "dv_model.yml") == document["declined"]


async def test_no_declines_no_file(tmp_path: Path) -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(dv_model=_cited_model()))
    cli.write_outputs(state, tmp_path)
    assert not (tmp_path / "metadata" / "bridge_decisions.yml").exists()
    assert load_declined_bridges(tmp_path) == []
    assert load_declined_bridges(tmp_path / "nowhere") == []


# ── T6: a declined path the operator builds after all leaves the list ──────────────────────
async def test_a_declined_path_built_by_the_operator_leaves_the_list(tmp_path: Path) -> None:
    path = propose_bridge_paths(_cited_model())[0].path
    state = await CodeGeneratorAgent().run(_on(declined_bridges=[path]))
    apply_human_decision(state, {"accept": True, "bridges": {path: True}})  # named again
    cli.write_outputs(state, tmp_path)
    assert path not in load_declined_bridges(tmp_path)


# ── T7: both extension paths hand the declines to the run ──────────────────────────────────
def test_the_cli_and_the_workbench_pass_the_declines() -> None:
    assert "declined_bridges" in inspect.signature(cli._run_pipeline).parameters
    assert "load_declined_bridges(existing)" in inspect.getsource(cli)
    assert "load_declined_bridges(existing_dir)" in inspect.getsource(runs)


def test_bounds_fixture_is_dated() -> None:  # keeps the shared fixture's meaning explicit
    assert BOUNDS["as_of_start"] == date(2026, 1, 1)
