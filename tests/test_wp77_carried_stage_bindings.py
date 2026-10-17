"""WP77 — a stage's binding travels with the model (spec §3). Committed before the change,
failing. The fixture is the twentieth chain's shape in miniature: `hub_purchase_order` built from
`PurchaseOrderHeader` (no name match), bound by override in its own step and lost in the next."""
from __future__ import annotations

from pathlib import Path

import yaml

from eval.run import write_step_vault
from vault_agent import cli
from vault_agent.agents.staging_generator import build_staging
from vault_agent.existing_model import (
    dump_source_catalogue,
    load_carried_bindings,
    stage_bindings,
)
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import DVModel, FlagKind, SourceTable, VaultAgentState

STEP1 = [
    SourceTable(table="PurchaseOrderHeader",
                columns=["PurchaseOrderID", "VendorID", "OrderDate", "TotalDue"],
                schema="Purchasing"),
]
STEP2 = [
    SourceTable(table="SalesOrderHeader", columns=["SalesOrderID", "SalesOrderNumber", "Status"],
                schema="Sales"),
]
PO_BINDING = {normalize_identifier("purchase_order"): "PurchaseOrderHeader"}


def _model1() -> DVModel:
    return DVModel.model_validate({
        "hubs": [{"name": "hub_purchase_order", "business_key": "PurchaseOrderID",
                  "source_entity": "PurchaseOrderHeader", "description": "x"}],
        "links": [],
        "satellites": [{"name": "sat_purchase_order_details", "parent": "hub_purchase_order",
                        "attributes": ["OrderDate", "TotalDue"],
                        "source_table": "PurchaseOrderHeader", "description": "x"}],
    })


def _model2() -> DVModel:
    m = _model1().model_dump()
    m["hubs"].append({"name": "hub_sales_order", "business_key": "SalesOrderNumber",
                      "source_entity": "SalesOrderHeader", "description": "x"})
    return DVModel.model_validate(m)


# ── §3.1 / §3.2 the catalogue carries the bindings ─────────────────────────────────────────
def test_the_catalogue_renders_and_loads_stage_bindings(tmp_path: Path) -> None:
    text = dump_source_catalogue(STEP1, {"stg_purchase_order": "PurchaseOrderHeader"})
    parsed = yaml.safe_load(text)
    assert parsed["stage_bindings"] == {"stg_purchase_order": "PurchaseOrderHeader"}
    assert [t["table"] for t in parsed["source_schemas"]] == ["PurchaseOrderHeader"]
    meta = tmp_path / "metadata"
    meta.mkdir()
    (meta / "source_catalogue.yml").write_text(text, encoding="utf-8")
    assert load_carried_bindings(tmp_path) == {"stg_purchase_order": "PurchaseOrderHeader"}
    assert load_carried_bindings(meta / "dv_model.yml") == {"stg_purchase_order": "PurchaseOrderHeader"}
    (meta / "source_catalogue.yml").write_text(dump_source_catalogue(STEP1), encoding="utf-8")
    assert load_carried_bindings(tmp_path) == {}  # an output before WP77
    assert load_carried_bindings(tmp_path / "nowhere") == {}


def test_stage_bindings_reads_the_declared_relations_from_the_staging_metadata() -> None:
    metadata = {
        "stg_purchase_order": {"source_model": {"raw": "PurchaseOrderHeader"},
                               "source_binding": "declared"},
        "stg_vendor": {"source_model": "Vendor", "source_binding": "declared"},
        "stg_vendor_product": {"source_model": {"inferred": "raw_vendor_product"},
                               "source_binding": "inferred"},
    }
    assert stage_bindings(metadata) == {"stg_purchase_order": "PurchaseOrderHeader",
                                        "stg_vendor": "Vendor"}


# ── §3.3 staging keeps a carried binding ───────────────────────────────────────────────────
def test_a_carried_binding_binds_what_the_next_step_cannot_resolve() -> None:
    first = build_staging(_model1(), STEP1, source_overrides=PO_BINDING)
    assert first.metadata["stg_purchase_order"]["source_binding"] == "declared"
    carried = stage_bindings(first.metadata)
    assert carried["stg_purchase_order"] == "PurchaseOrderHeader"

    today = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1)
    assert "inferred: 'raw_purchase_order'" in today.models["stg_purchase_order"]  # the defect

    kept = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1,
                         carried_bindings=carried)
    stage = kept.models["stg_purchase_order"]
    assert "source_model:\n" in stage and "'PurchaseOrderHeader'" in stage
    assert "raw_purchase_order" not in stage
    assert kept.metadata["stg_purchase_order"]["source_binding"] == "declared"
    assert [f for f in kept.flags if f.asset == "stg_purchase_order"] == []
    assert "schema: Purchasing" in kept.scaffolding["models/staging/sources.yml"]


def test_a_carried_binding_to_a_relation_lacking_a_hashed_column_is_refused() -> None:
    wrong = {"stg_purchase_order": "SalesOrderHeader"}  # lacks PURCHASEORDERID
    result = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1,
                           carried_bindings=wrong)
    assert "inferred: 'raw_purchase_order'" in result.models["stg_purchase_order"]
    [flag] = [f for f in result.flags if f.kind == FlagKind.BINDING_REJECTED]
    assert flag.asset == "stg_purchase_order" and flag.reason == "SalesOrderHeader"


def test_this_runs_override_wins_over_the_carried_binding() -> None:
    other = [SourceTable(table="PurchaseOrderArchive",
                         columns=["PurchaseOrderID", "OrderDate", "TotalDue"], schema="Archive")]
    result = build_staging(_model2(), STEP2 + other, existing=_model1(), carried=STEP1,
                           carried_bindings={"stg_purchase_order": "PurchaseOrderHeader"},
                           source_overrides={normalize_identifier("purchase_order"):
                                             "PurchaseOrderArchive"})
    assert "'PurchaseOrderArchive'" in result.models["stg_purchase_order"]


# ── §3.4 the writers and the state ─────────────────────────────────────────────────────────
def test_write_outputs_and_the_harness_write_the_bindings_the_loader_reads(tmp_path: Path) -> None:
    first = build_staging(_model1(), STEP1, source_overrides=PO_BINDING)
    state = VaultAgentState(source_schemas=STEP1, dv_model=_model1())
    state.artifacts.staging_models = first.models
    state.artifacts.scaffolding = first.scaffolding
    state.artifacts.automatedv_yaml = {"hubs": {}, "staging": first.metadata}
    cli.write_outputs(state, tmp_path / "cli")
    assert load_carried_bindings(tmp_path / "cli") == {
        "stg_purchase_order": "PurchaseOrderHeader",
        "stg_purchase_order_details": "PurchaseOrderHeader",
    }
    write_step_vault(state, tmp_path / "step1")
    assert load_carried_bindings(tmp_path / "step1") == load_carried_bindings(tmp_path / "cli")
    second = VaultAgentState(source_schemas=STEP2, carried_schemas=STEP1,
                             carried_bindings=load_carried_bindings(tmp_path / "cli"))
    assert second.carried_bindings["stg_purchase_order"] == "PurchaseOrderHeader"
