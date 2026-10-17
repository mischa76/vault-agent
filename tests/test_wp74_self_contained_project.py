"""WP74 — a brownfield step's project is self-contained (spec §3). Committed before the change,
failing. Keyless."""
from __future__ import annotations

from pathlib import Path

import yaml

from tests.test_cli import _sqlite_stub_agents
from vault_agent import cli
from vault_agent.agents.staging_generator import build_staging, unresolved_stage_refs
from vault_agent.existing_model import load_existing_catalogue
from vault_agent.graph import build_graph
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import DVModel, SourceTable, VaultAgentState

STEP1 = [
    SourceTable(table="Customer", columns=["CustomerID", "Name", "ModifiedDate"], schema="Sales"),
]
STEP2 = [
    SourceTable(table="Account", columns=["AccountID", "CustomerID", "Balance"], schema="Bank",
                foreign_keys=[{"columns": ["CustomerID"], "references_table": "Customer",
                               "references_columns": ["CustomerID"]}]),
]


def _model1() -> DVModel:
    return DVModel.model_validate({
        "hubs": [{"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
                  "description": "x"}],
        "links": [],
        "satellites": [{"name": "sat_customer_details", "parent": "hub_customer",
                        "attributes": ["Name"], "source_table": "Customer", "description": "x"}],
    })


def _model2() -> DVModel:
    m = _model1().model_dump()
    m["hubs"].append({"name": "hub_account", "business_key": "AccountID", "source_entity": "Account",
                      "description": "x"})
    m["links"].append({"name": "link_account_customer", "connected_hubs": ["hub_account", "hub_customer"],
                       "description": "x"})
    m["satellites"].append({"name": "sat_account_details", "parent": "hub_account",
                            "attributes": ["Balance"], "source_table": "Account", "description": "x"})
    return DVModel.model_validate(m)


def test_write_outputs_writes_the_source_catalogue_and_the_loader_reads_it(tmp_path: Path) -> None:
    state = VaultAgentState(source_schemas=STEP1, dv_model=_model1())
    state.artifacts.automatedv_yaml = {"hubs": {}}  # enough for write_outputs to write metadata/
    cli.write_outputs(state, tmp_path)
    path = tmp_path / "metadata" / "source_catalogue.yml"
    assert path.exists()
    tables = load_source_schemas(path)
    assert [(t.table, t.schema_name, t.column_names) for t in tables] == [
        ("Customer", "Sales", ["CustomerID", "Name", "ModifiedDate"])
    ]
    assert load_existing_catalogue(tmp_path) and load_existing_catalogue(tmp_path / "nowhere") == []


def test_staging_keeps_the_earlier_increments_bindings_when_the_catalogue_is_carried() -> None:
    carried = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1)
    stage = carried.models["stg_customer"]
    assert "source_model:\n" in stage and "'Customer'" in stage  # the source() mapping form
    sat = carried.models["stg_customer_details"]
    assert "source_model:\n" in sat and "'Customer'" in sat
    sources = carried.scaffolding["models/staging/sources.yml"]
    assert "schema: Sales" in sources and "schema: Bank" in sources
    assert not [n for n, sql in carried.models.items() if "raw_customer" in sql]
    assert unresolved_stage_refs(carried.models, sources) == []

    degraded = build_staging(_model2(), STEP2, existing=_model1())  # today's shape, the contrast
    assert "schema: Sales" not in degraded.scaffolding["models/staging/sources.yml"]
    assert unresolved_stage_refs(
        degraded.models, degraded.scaffolding["models/staging/sources.yml"]
    ) == ["stg_customer_details"]  # the satellite's bare `Customer`, a ref dbt cannot resolve


def test_carried_schemas_never_enter_source_schemas(tmp_path: Path) -> None:
    state = VaultAgentState(source_schemas=STEP2, carried_schemas=STEP1, dv_model=_model2())
    assert [t.table for t in state.source_schemas] == ["Account"]
    assert [t.table for t in state.carried_schemas] == ["Customer"]


async def test_the_cli_loads_the_catalogue_of_an_existing_output(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=False)))
    first = VaultAgentState(source_schemas=STEP1, dv_model=_model1())
    first.artifacts.automatedv_yaml = {"hubs": {}}
    cli.write_outputs(first, tmp_path / "step1")
    doc = tmp_path / "req.md"
    doc.write_text("# Requirements\n\nAn account belongs to a customer.\n", encoding="utf-8")
    state, _paused, _thread = await cli._run_pipeline(
        doc, tmp_path / "step2", STEP2,
        existing_model=cli.load_existing_model(tmp_path / "step1"),
        existing_source=str(tmp_path / "step1"),
        carried_schemas=load_existing_catalogue(tmp_path / "step1"),
    )
    assert [t.table for t in state.carried_schemas] == ["Customer"]
    assert [t.table for t in state.source_schemas] == ["Account"]
    written = yaml.safe_load((tmp_path / "step2" / "metadata" / "source_catalogue.yml").read_text())
    assert sorted(t["table"] for t in written["source_schemas"]) == ["Account", "Customer"]
