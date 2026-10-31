"""WP103 — the derived AdventureWorks schemas carry the extract's nullability (spec §2, C37).
Committed red before the change. Keyless throughout: P1 on the derivation against the extract,
P2 on the shipped cases and their drafted copies, P3 on WP94's gate over the shipped Sales case."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from eval.adventureworks.derive import build_source_schema, case_dir_name, subject_areas
from eval.datasets import DATASETS_ROOT
from tests.test_wp94_optional_participant import _hubs, _link
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import DVModel, ValidationIssue, VaultAgentState

_EXTRACT = DATASETS_ROOT / "adventureworks" / "schema_extract.json"
_SALES = DATASETS_ROOT / "adventureworks_sales" / "source_schema.yml"


def _extract() -> dict:  # type: ignore[type-arg]
    return json.loads(_EXTRACT.read_text(encoding="utf-8"))


# ── P1 the derivation ───────────────────────────────────────────────────────────────────


def test_p1_every_derived_column_states_the_extracts_nullability() -> None:
    """Transcribed, never curated (WP30 §2.3): the extract's `nullable` for every column of the
    five business schemas — 465 columns, 77 of them nullable — and nothing decided here."""
    extract = _extract()
    truth = {
        (t["schema"], t["name"], c["name"]): c["nullable"]
        for t in extract["tables"]
        for c in t["columns"]
    }
    checked = nullable = 0
    for schema in subject_areas(extract):
        for table in build_source_schema(extract, schema)["source_schemas"]:
            for column in table["columns"]:
                assert column["nullable"] is truth[(schema, table["table"], column["name"])]
                checked += 1
                nullable += column["nullable"]
    assert checked == 465
    assert nullable == 77


def test_p1_the_column_entry_keeps_the_house_formats_key_order() -> None:
    """`name, type, nullable, comment` — the order `source_schema_reader._entry` writes (WP98),
    so a derived file and a file read from a source are one shape."""
    extract = _extract()
    tables = build_source_schema(extract, "Sales")["source_schemas"]
    header = next(t for t in tables if t["table"] == "SalesOrderHeader")
    by_name = {c["name"]: c for c in header["columns"]}
    assert list(by_name["CurrencyRateID"]) == ["name", "type", "nullable", "comment"]
    assert by_name["CurrencyRateID"]["nullable"] is True
    assert by_name["CustomerID"]["nullable"] is False
    undescribed = [
        c for schema in subject_areas(extract)
        for t in build_source_schema(extract, schema)["source_schemas"]
        for c in t["columns"] if "comment" not in c
    ]
    assert undescribed, "the extract has columns Microsoft left undescribed"
    assert all(list(c) == ["name", "type", "nullable"] for c in undescribed)


# ── P2 the shipped cases ────────────────────────────────────────────────────────────────


def test_p2_the_shipped_cases_declare_nullability_and_the_drafted_copies_match() -> None:
    """Every derived case says it for every column; the C1 cases stay byte-identical copies
    (their `dataset.yml` says so); the combined case counts the same 77."""
    extract = _extract()
    for schema in subject_areas(extract):
        shipped = DATASETS_ROOT / case_dir_name(schema) / "source_schema.yml"
        tables = load_source_schemas(shipped)
        assert all(c.nullable is not None for t in tables for c in t.column_refs), schema
        drafted = DATASETS_ROOT / f"adventureworks_drafted_{schema.lower()}" / "source_schema.yml"
        assert drafted.read_bytes() == shipped.read_bytes(), schema
    header = next(t for t in load_source_schemas(_SALES) if t.table == "SalesOrderHeader")
    columns = {c.name: c for c in header.column_refs}
    assert columns["CurrencyRateID"].nullable is True
    assert columns["CustomerID"].nullable is False
    full = load_source_schemas(DATASETS_ROOT / "adventureworks_full" / "source_schema.yml")
    assert sum(bool(c.nullable) for t in full for c in t.column_refs) == 77


# ── P3 WP94's gate over the shipped case ────────────────────────────────────────────────


def _gate(schema: Path) -> list[ValidationIssue]:
    state = VaultAgentState(
        dv_model=DVModel(hubs=_hubs(), links=[_link()]),
        source_schemas=list(load_source_schemas(schema)),
    )
    state = asyncio.run(ValidatorAgent().run(state))
    return [
        i for i in state.validation_report.issues if i.code.endswith("LINK_OPTIONAL_PARTICIPANT")
    ]


def test_p3_wp94s_gate_refuses_on_the_derived_sales_case() -> None:
    """WP94's miniature — its hubs and three-way link — over the shipped Sales case instead of
    the hand-written tables: the currency-rate participation is the error with the own-link
    remedy, not the warning both chains of 2026-10-30 got; the customer's integer participation
    is never named."""
    issues = _gate(_SALES)
    assert [(i.severity, i.code) for i in issues] == [("error", "E_LINK_OPTIONAL_PARTICIPANT")]
    assert "hub_currency_rate" in issues[0].message
    assert "hub_customer" not in issues[0].message
    assert issues[0].remedy is not None
    assert "link_sales_order_header_currency_rate" in issues[0].remedy
