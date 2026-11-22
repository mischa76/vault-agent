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
from vault_agent.rules.dv2_rules import normalize_identifier
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
    m["hubs"].append({"name": "hub_account", "business_key": "AccountID",
                      "source_entity": "Account", "description": "x"})
    m["links"].append({"name": "link_account_customer",
                       "connected_hubs": ["hub_account", "hub_customer"], "description": "x"})
    m["satellites"].append({"name": "sat_account_details", "parent": "hub_account",
                            "attributes": ["Balance"], "source_table": "Account",
                            "description": "x"})
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


# The link's stage is bound the way the mapper's re-bind binds it (its relation is Account,
# which carries both keys); without an override it would be inferred, which dbt cannot ref.
LINK_BINDING = {normalize_identifier("account_customer"): "Account"}


def test_staging_keeps_the_earlier_increments_bindings_when_the_catalogue_is_carried() -> None:
    carried = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1,
                            source_overrides=LINK_BINDING)
    stage = carried.models["stg_customer"]
    assert "source_model:\n" in stage and "'Customer'" in stage  # the source() mapping form
    sat = carried.models["stg_customer_details"]
    assert "source_model:\n" in sat and "'Customer'" in sat
    sources = carried.scaffolding["models/staging/sources.yml"]
    assert "schema: Sales" in sources and "schema: Bank" in sources
    assert not [n for n, sql in carried.models.items() if "raw_customer" in sql]
    assert unresolved_stage_refs(carried.models, sources) == []

    degraded = build_staging(_model2(), STEP2, existing=_model1(),
                             source_overrides=LINK_BINDING)  # yesterday's shape, the contrast
    assert "schema: Sales" not in degraded.scaffolding["models/staging/sources.yml"]
    assert "stg_customer_details" in unresolved_stage_refs(
        degraded.models, degraded.scaffolding["models/staging/sources.yml"]
    )  # the satellite's bare `Customer`, a ref dbt cannot resolve


def test_an_inferred_relation_counts_as_unresolved_because_dbt_refs_it() -> None:
    models = {"stg_x": "source_model: 'raw_x'\n", "stg_y": "source_model: 'stg_x'\n"}
    assert unresolved_stage_refs(models, "version: 2\nsources: []\n") == ["stg_x"]


def test_a_translation_views_jinja_refs_are_checked_too() -> None:
    sources = ("version: 2\nsources:\n  - name: raw\n    schema: S\n    tables:\n"
               "      - name: Product\n")
    models = {
        "stg_a_via_product": "select * from {{ ref('raw_a') }} t\n"
                             "left join {{ source('raw', 'Product') }} r on 1=1\n",
        "stg_b_via_product": "select * from {{ ref('stg_c') }} t\n"
                             "left join {{ source('raw', 'Product') }} r on 1=1\n",
        "stg_c": "source_model:\n  raw: 'Product'\n",
        "stg_d_via_other": "select * from {{ ref('stg_c') }} t\n"
                           "left join {{ source('raw', 'Missing') }} r on 1=1\n",
    }
    assert unresolved_stage_refs(models, sources) == ["stg_a_via_product", "stg_d_via_other"]


def test_carried_schemas_never_enter_source_schemas(tmp_path: Path) -> None:
    state = VaultAgentState(source_schemas=STEP2, carried_schemas=STEP1, dv_model=_model2())
    assert [t.table for t in state.source_schemas] == ["Account"]
    assert [t.table for t in state.carried_schemas] == ["Customer"]


async def test_the_cli_loads_the_catalogue_of_an_existing_output(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    monkeypatch.setattr(
        cli, "build_graph", lambda: build_graph(_sqlite_stub_agents(block_signoff=False))
    )
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
    cli.write_outputs(state, tmp_path / "step2")  # what the `run` command does after the pipeline
    written = yaml.safe_load((tmp_path / "step2" / "metadata" / "source_catalogue.yml").read_text())
    assert sorted(t["table"] for t in written["source_schemas"]) == ["Account", "Customer"]


def test_the_scorer_and_the_metric_read_the_written_project() -> None:
    from eval.scorers import VACUOUS_PREFIX, project_self_contained

    case = type("Case", (), {})()
    empty = VaultAgentState()
    assert project_self_contained(empty, case).details.startswith(VACUOUS_PREFIX)
    carried = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1,
                            source_overrides=LINK_BINDING)
    good = VaultAgentState(dv_model=_model2())
    good.artifacts.staging_models = carried.models
    good.artifacts.scaffolding = carried.scaffolding
    assert project_self_contained(good, case).score == 1.0
    degraded = build_staging(_model2(), STEP2, existing=_model1(),
                             source_overrides=LINK_BINDING)
    bad = VaultAgentState(dv_model=_model2())
    bad.artifacts.staging_models = degraded.models
    bad.artifacts.scaffolding = degraded.scaffolding
    verdict = project_self_contained(bad, case)
    assert verdict.score == 0.0 and "stg_customer_details" in verdict.details


def test_the_harness_can_keep_a_steps_full_output(tmp_path: Path) -> None:
    from eval.run import keep_step_outputs

    carried = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1,
                            source_overrides=LINK_BINDING)
    state = VaultAgentState(source_schemas=STEP2, carried_schemas=STEP1, dv_model=_model2())
    state.artifacts.staging_models = carried.models
    state.artifacts.scaffolding = carried.scaffolding
    state.artifacts.automatedv_yaml = {"hubs": {}, "staging": carried.metadata}
    out = keep_step_outputs(tmp_path, "chain", "20261017T000000000000Z", 2, "bank", state)
    assert out == tmp_path / "chain" / "20261017T000000000000Z" / "step2_bank"
    assert (out / "dbt_project.yml").exists()
    assert (out / "models" / "staging" / "sources.yml").exists()
    assert (out / "metadata" / "source_catalogue.yml").exists()
    names = sorted(p.name for p in (out / "models" / "staging").glob("*.sql"))
    assert "stg_customer.sql" in names and "stg_account.sql" in names
