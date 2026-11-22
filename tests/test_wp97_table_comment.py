"""WP97 — a table's own comment in the house format (spec §4, C31). Committed red before the
change. Keyless throughout: P1 on a stub reader and WP96's SQLite fixture, P2 on the loader, P3 on
the two payloads that already carry column comments and the three surfaces that must stay inert,
P4 on the derivation against the extract."""
from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
import yaml
from sqlalchemy import event, inspect

from eval.adventureworks.derive import build_source_schema, subject_areas
from vault_agent.agents.entity_resolver import EntityResolverAgent
from vault_agent.agents.entity_resolver import _Concept as _ResolverConcept
from vault_agent.agents.source_mapper import SourceMapperAgent
from vault_agent.agents.source_mapper import _Concept as _MapperConcept
from vault_agent.existing_model import dump_source_catalogue
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.source_schema import load_source_schemas
from vault_agent.source_schema_reader import (
    InspectorReader,
    ReadColumn,
    ReadForeignKey,
    read_source_schema,
    render_source_schema,
)
from vault_agent.state import DVModel, SourceTable, VaultAgentState

_EXTRACT = Path(__file__).resolve().parents[1] / "eval/datasets/adventureworks/schema_extract.json"
_COMMENT = "  Customer information, one row per\n customer. "


class _Reader:
    """A reader with a table comment on one of two tables; ``saying=False`` cannot say."""

    default_schema = "dbo"

    def __init__(self, *, saying: bool = True) -> None:
        self.saying = saying

    def schema_names(self) -> list[str]:
        return ["dbo"]

    def table_names(self, schema: str) -> list[str]:
        return ["Customer", "Territory"]

    def view_names(self, schema: str) -> list[str]:
        return []

    def columns(self, table: str, schema: str) -> list[ReadColumn]:
        return [ReadColumn("ID", "int", False, None)]

    def primary_key(self, table: str, schema: str) -> list[str]:
        return ["ID"]

    def unique_keys(self, table: str, schema: str) -> list[list[str]]:
        return []

    def foreign_keys(self, table: str, schema: str) -> list[ReadForeignKey]:
        return []

    def table_comment(self, table: str, schema: str) -> str | None:
        if not self.saying:
            raise NotImplementedError
        return _COMMENT if table == "Customer" else None


# ── P1 the reader ───────────────────────────────────────────────────────────────────────


def test_p1_the_table_comment_is_transcribed_verbatim_and_a_dialect_that_cannot_say_records_none(
    tmp_path: Path,
) -> None:
    customer, territory = read_source_schema(_Reader(), schemas=["dbo"], database=None)
    assert customer.comment == _COMMENT, "verbatim, whitespace kept — the payload collapses it"
    assert territory.comment is None
    silent = read_source_schema(_Reader(saying=False), schemas=["dbo"], database=None)
    assert [t.comment for t in silent] == [None, None]

    text = render_source_schema([customer, territory], header="h")
    entries = yaml.safe_load(text)["source_schemas"]
    assert list(entries[0]) == ["table", "schema", "comment", "columns", "primary_key"]
    assert "comment" not in entries[1]
    path = tmp_path / "s.yml"
    path.write_text(text, encoding="utf-8")
    assert [t.comment for t in load_source_schemas(path)] == [_COMMENT, None]


def test_p1_sqlite_has_no_table_comments_and_the_file_says_nothing(tmp_path: Path) -> None:
    main, other = tmp_path / "main.db", tmp_path / "other.db"
    engine = sa.create_engine(f"sqlite:///{main}")

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection: object, _record: object) -> None:
        dbapi_connection.execute(f"ATTACH DATABASE '{other}' AS Other")  # type: ignore[attr-defined]

    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE "Customer" ("CustomerID" INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE "Other"."Territory" ("TerritoryID" INTEGER)')
    tables = read_source_schema(
        InspectorReader(inspect(engine)), schemas=["main", "Other"], database=None
    )
    assert [t.comment for t in tables] == [None, None]
    for entry in yaml.safe_load(render_source_schema(tables, header="h"))["source_schemas"]:
        assert "comment" not in entry


# ── P2 the loader and the model ─────────────────────────────────────────────────────────


def test_p2_a_table_entry_may_declare_a_comment_and_needs_not(tmp_path: Path) -> None:
    path = tmp_path / "s.yml"
    path.write_text(
        "source_schemas:\n"
        "  - table: Customer\n"
        "    comment: Customer information.\n"
        "    columns: [CustomerID]\n"
        "  - table: Territory\n"
        "    columns: [TerritoryID]\n",
        encoding="utf-8",
    )
    customer, territory = load_source_schemas(path)
    assert customer.comment == "Customer information."
    assert territory.comment is None
    assert SourceTable(table="x", columns=["a"]).comment is None
    assert SourceTable.model_validate({"table": "x", "columns": ["a"]}).comment is None


# ── P3 the two payloads, and the surfaces that stay inert ──────────────────────────────


def _schemas(*, commented: bool) -> list[SourceTable]:
    return [
        SourceTable(
            table="Customer",
            columns=[{"name": "CustomerID", "type": "int", "comment": "Primary key."}],
            comment=_COMMENT if commented else None,
        ),
        SourceTable(table="Territory", columns=["TerritoryID"]),
    ]


def test_p3_the_resolver_payload_carries_the_commented_tables_only() -> None:
    agent = EntityResolverAgent.__new__(EntityResolverAgent)
    concepts = [_ResolverConcept("customer", "Customer")]
    with_ = json.loads(agent._payload(
        VaultAgentState(existing_model=DVModel(), source_schemas=_schemas(commented=True)),
        concepts,
    ))
    without = json.loads(agent._payload(
        VaultAgentState(existing_model=DVModel(), source_schemas=_schemas(commented=False)),
        concepts,
    ))
    assert with_["source_tables"] == [
        {"table": "Customer", "comment": "Customer information, one row per customer."}
    ]
    assert "source_tables" not in without
    del with_["source_tables"]
    assert with_ == without, "the comment adds one key and changes nothing else"


def test_p3_the_mapper_payload_carries_the_commented_tables_only() -> None:
    agent = SourceMapperAgent.__new__(SourceMapperAgent)
    concepts = [_MapperConcept("customer", "Customer", "business_key")]
    with_ = json.loads(agent._payload(
        VaultAgentState(source_schemas=_schemas(commented=True)), concepts
    ))
    without = json.loads(agent._payload(
        VaultAgentState(source_schemas=_schemas(commented=False)), concepts
    ))
    assert with_["source_tables"] == [
        {"table": "Customer", "comment": "Customer information, one row per customer."}
    ]
    assert "source_tables" not in without
    del with_["source_tables"]
    assert with_ == without


def test_p3_the_modeler_prompt_and_the_carried_catalogue_never_see_it() -> None:
    """Spec §2 rule 2: a change to the modeler's input is a measured change (WP34 §3.8). If the
    owner wants the modeler to read table comments, that is its own WP with a live run, and this
    guard is updated deliberately."""
    with_, without = _schemas(commented=True), _schemas(commented=False)
    assert render_schema_prompt_section(with_) == render_schema_prompt_section(without)
    assert dump_source_catalogue(with_) == dump_source_catalogue(without)
    assert "one row per" not in render_schema_prompt_section(with_) + dump_source_catalogue(with_)


# ── P4 the derivation ───────────────────────────────────────────────────────────────────


def test_p4_the_derivation_carries_the_tables_description_verbatim() -> None:
    extract = json.loads(_EXTRACT.read_text(encoding="utf-8"))
    upstream = {(t["schema"], t["name"]): t["description"] for t in extract["tables"]}
    described, blank = 0, []
    for schema in subject_areas(extract):
        for entry in build_source_schema(extract, schema)["source_schemas"]:
            text = upstream[(schema, entry["table"])]
            if text:
                assert entry["comment"] == text
                described += 1
            else:
                assert "comment" not in entry
                blank.append(f"{schema}.{entry['table']}")
    assert described == 66, described
    assert len(blank) == 2, blank
