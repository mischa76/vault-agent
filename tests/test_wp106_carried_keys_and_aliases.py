"""WP106 — the eval harness carries `stage_aliases` as the CLI and the workbench do (C40), and
the carried catalogue carries a table's declared keys (C41). Committed red before the change.
Keyless."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eval import run as run_mod
from eval.datasets import DATASETS_ROOT, load_eval_case
from eval.run import write_step_vault
from tests.test_cli import _sqlite_stub_agents
from tests.test_wp95_role_column_from_fk import _hubs, _sales_person, _territory_link
from vault_agent.agents.staging_generator import build_staging
from vault_agent.existing_model import (
    dump_source_catalogue,
    load_carried_aliases,
    load_existing_catalogue,
)
from vault_agent.graph import build_graph
from vault_agent.state import DVModel, FlagKind, SourceTable, VaultAgentState

STAGE = "stg_sales_person_sales_territory"
ALIAS = {"SALES_PERSON_BUSINESSENTITYID": "BUSINESSENTITYID"}

KEYED = SourceTable(table="BillOfMaterials", schema="Production", columns=[
    {"name": "BillOfMaterialsID", "type": "int"}, {"name": "ProductAssemblyID", "type": "int"},
    {"name": "ComponentID", "type": "int"}, {"name": "StartDate", "type": "datetime"},
], primary_key=["BillOfMaterialsID"],
    unique_keys=[["ProductAssemblyID", "ComponentID", "StartDate"]],
    foreign_keys=[
        {"columns": ["ProductAssemblyID"], "references_table": "Product",
         "references_columns": ["ProductID"], "references_schema": "Production"},
        {"columns": ["ComponentID"], "references_table": "Product",
         "references_columns": ["ProductID"]},
    ])


# ── C41: the catalogue carries the declared keys ──────────────────────────────────────────
def test_the_catalogue_carries_primary_unique_and_foreign_keys_in_the_house_shape() -> None:
    entry = yaml.safe_load(dump_source_catalogue([KEYED]))["source_schemas"][0]
    assert entry["primary_key"] == ["BillOfMaterialsID"]
    assert entry["unique_keys"] == [["ProductAssemblyID", "ComponentID", "StartDate"]]
    assert entry["foreign_keys"] == [
        {"columns": ["ProductAssemblyID"], "references_table": "Product",
         "references_columns": ["ProductID"], "references_schema": "Production"},
        {"columns": ["ComponentID"], "references_table": "Product",
         "references_columns": ["ProductID"]},
    ]
    assert list(entry) == [
        "table", "columns", "schema", "foreign_keys", "primary_key", "unique_keys",
    ]


def test_the_loader_reads_the_keys_back(tmp_path: Path) -> None:
    state = VaultAgentState(source_schemas=[KEYED])
    write_step_vault(state, tmp_path / "step1")
    [table] = load_existing_catalogue(tmp_path / "step1")
    assert table.primary_key == KEYED.primary_key and table.unique_keys == KEYED.unique_keys
    assert [fk.model_dump() for fk in table.foreign_keys] == [
        fk.model_dump() for fk in KEYED.foreign_keys
    ]


def test_a_keyless_table_stays_byte_identical() -> None:
    plain = SourceTable(table="Customer", schema="Sales", columns=["CustomerID", "PersonID"])
    assert dump_source_catalogue([plain]) == (
        "source_schemas:\n- table: Customer\n  columns:\n  - CustomerID\n  - PersonID\n"
        "  schema: Sales\n"
    )


def test_wp95_derives_the_role_column_on_a_relation_carried_through_the_catalogue(
    tmp_path: Path,
) -> None:
    """The twenty-third chain's step 5 could not derive a role column on the carried
    `ProductVendor` where step 4 could: the catalogue had dropped its foreign keys."""
    write_step_vault(VaultAgentState(source_schemas=[_sales_person()]), tmp_path / "step1")
    carried = load_existing_catalogue(tmp_path / "step1")
    model = DVModel(hubs=_hubs(), links=[_territory_link()], satellites=[])
    result = build_staging(model, [], carried=carried, carried_bindings={STAGE: "SalesPerson"})
    assert not [f for f in result.flags if f.kind == FlagKind.BINDING_REJECTED and f.asset == STAGE]
    assert "'SalesPerson'" in result.models[STAGE]
    assert "SALES_PERSON_BUSINESSENTITYID: 'BUSINESSENTITYID'" in result.models[STAGE]


# ── C40: the harness carries the aliases ──────────────────────────────────────────────────
def _step_with_alias(where: Path) -> Path:
    state = VaultAgentState(source_schemas=[_sales_person()],
                            dv_model=DVModel(hubs=_hubs(), links=[_territory_link()]))
    state.artifacts.automatedv_yaml = {"staging": {STAGE: {
        "source_binding": "declared", "source_model": {"raw": "SalesPerson"},
        "role_columns": dict(ALIAS),
    }}}
    write_step_vault(state, where)
    return where


def test_write_step_vault_writes_the_aliases_the_loader_reads(tmp_path: Path) -> None:
    step = _step_with_alias(tmp_path / "step1")
    assert load_carried_aliases(step) == {STAGE: ALIAS}


async def test_run_case_once_hands_the_step_the_previous_steps_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = _step_with_alias(tmp_path / "step1")
    monkeypatch.setattr(
        run_mod, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=False))
    )
    case = load_eval_case(DATASETS_ROOT / "adventureworks_humanresources" / "dataset.yml")
    state = await run_mod.run_case_once(case.model_copy(update={"existing": step}))
    assert state.carried_bindings == {STAGE: "SalesPerson"}
    assert state.carried_aliases == {STAGE: ALIAS}
