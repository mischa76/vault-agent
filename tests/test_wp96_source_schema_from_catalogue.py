"""WP96 — the declared source schema read from the source system's catalogue (spec §4, C27
stage 1). Committed red before the change. Keyless: P1 on SQLite with an attached schema (the
real SQLAlchemy reader), the comment and unknown-type paths through a stub reader, P2 through
Typer's runner, P3 on the DDL instrument's text."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml
from sqlalchemy import event, inspect
from sqlalchemy.sql import sqltypes
from typer.testing import CliRunner

from vault_agent.cli import app
from vault_agent.source_schema import load_source_schemas
from vault_agent.source_schema_reader import (
    InspectorReader,
    ReadColumn,
    ReadForeignKey,
    hidden_url,
    read_source_schema,
    render_source_schema,
)
from vault_agent.state import ForeignKeyRef, SourceTable

_EXTRACT = Path(__file__).resolve().parents[1] / "eval/datasets/adventureworks/schema_extract.json"

_DDL = [
    'CREATE TABLE "Customer" ('
    '"CustomerID" INTEGER NOT NULL, "TerritoryID" INTEGER, '
    '"AccountNumber" VARCHAR(10) NOT NULL, "rowguid" CHAR(36) NOT NULL, '
    'PRIMARY KEY ("CustomerID"), CONSTRAINT "AK_Customer_AccountNumber" UNIQUE ("AccountNumber"))',
    'CREATE UNIQUE INDEX "AK_Customer_rowguid" ON "Customer"("rowguid")',
    'CREATE TABLE "SalesOrderHeader" ('
    '"SalesOrderID" INTEGER NOT NULL, "RevisionNumber" INTEGER NOT NULL, '
    '"CustomerID" INTEGER NOT NULL, "Total" NUMERIC(19, 4), '
    'PRIMARY KEY ("SalesOrderID", "RevisionNumber"), '
    'FOREIGN KEY ("CustomerID") REFERENCES "Customer"("CustomerID"))',
    'CREATE VIEW "v_orders" AS SELECT "SalesOrderID", "Total" FROM "SalesOrderHeader"',
]
# A second, attached schema whose foreign key crosses into the first — SQLite names the referred
# schema here; for a key inside the default schema it says nothing, and the reader fills it.
_DDL_OTHER = [
    'CREATE TABLE "Other"."Territory" ("TerritoryID" INTEGER NOT NULL PRIMARY KEY, '
    '"Name" VARCHAR(50) NOT NULL)',
    'CREATE TABLE "Other"."Assignment" ("SalesOrderID" INTEGER NOT NULL, '
    '"RevisionNumber" INTEGER NOT NULL, "TerritoryID" INTEGER, '
    'PRIMARY KEY ("SalesOrderID", "RevisionNumber"), '
    'FOREIGN KEY ("TerritoryID") REFERENCES "Territory"("TerritoryID"), '
    'FOREIGN KEY ("SalesOrderID", "RevisionNumber") '
    'REFERENCES "main"."SalesOrderHeader"("SalesOrderID", "RevisionNumber"))',
]


@pytest.fixture
def engine(tmp_path: Path) -> sa.Engine:
    main, other = tmp_path / "main.db", tmp_path / "other.db"
    engine = sa.create_engine(f"sqlite:///{main}")

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection: object, _record: object) -> None:
        dbapi_connection.execute(f"ATTACH DATABASE '{other}' AS Other")  # type: ignore[attr-defined]

    with engine.begin() as connection:
        for statement in [*_DDL, *_DDL_OTHER]:
            connection.exec_driver_sql(statement)
    return engine


def _read(engine: sa.Engine, schemas: list[str], *, views: bool = False) -> list[SourceTable]:
    return read_source_schema(
        InspectorReader(inspect(engine)), schemas=schemas, database="main.db", views=views
    )


# --- P1: the SQLite miniature through the real reader ------------------------------------------


def test_p1_tables_columns_keys_and_foreign_keys_are_transcribed(engine: sa.Engine) -> None:
    tables = _read(engine, ["main", "Other"])
    assert [(t.schema_name, t.table) for t in tables] == [
        ("Other", "Assignment"), ("Other", "Territory"), ("main", "Customer"),
        ("main", "SalesOrderHeader"),
    ], "sorted by (schema, table); a view is not a table"
    customer = tables[2]
    assert customer.database == "main.db"
    assert [(c.name, c.type, c.nullable) for c in customer.column_refs] == [
        ("CustomerID", "integer", False), ("TerritoryID", "integer", True),
        ("AccountNumber", "varchar(10)", False), ("rowguid", "char(36)", False),
    ], "ordinal order, the dialect's spelling lowercased, nullable always"
    assert customer.primary_key == ["CustomerID"]
    assert customer.unique_keys == [["AccountNumber"], ["rowguid"]], (
        "the unique constraint and the unique index, not the primary key"
    )
    header = tables[3]
    assert header.primary_key == ["SalesOrderID", "RevisionNumber"]
    assert header.unique_keys == []
    assert header.foreign_keys == [
        ForeignKeyRef(
            columns=["CustomerID"], references_table="Customer",
            references_columns=["CustomerID"], references_schema="main",
        )
    ], "a referred schema the catalogue omits is the default schema, filled in"
    assignment = tables[0]
    assert assignment.foreign_keys == [
        ForeignKeyRef(
            columns=["SalesOrderID", "RevisionNumber"], references_table="SalesOrderHeader",
            references_columns=["SalesOrderID", "RevisionNumber"], references_schema="main",
        ),
        ForeignKeyRef(
            columns=["TerritoryID"], references_table="Territory",
            references_columns=["TerritoryID"], references_schema="Other",
        ),
    ], "composite keys whole, sorted by (columns, referenced table)"
    assert header.column_refs[3].type == "numeric(19, 4)"


def test_p1_views_only_on_request(engine: sa.Engine) -> None:
    assert [t.table for t in _read(engine, ["main"], views=True)] == [
        "Customer", "SalesOrderHeader", "v_orders",
    ]
    view = _read(engine, ["main"], views=True)[2]
    assert [c.name for c in view.column_refs] == ["SalesOrderID", "Total"]
    assert view.primary_key == [] and view.foreign_keys == [] and view.unique_keys == []


def test_p1_the_file_loads_through_the_house_loader_and_is_deterministic(
    engine: sa.Engine, tmp_path: Path
) -> None:
    tables = _read(engine, ["main", "Other"])
    header = "read by vault-agent source-schema from sqlite:///main.db — schemas main, Other"
    text = render_source_schema(tables, header=header)
    assert text.startswith("# " + header), "the provenance is a comment the loader ignores"
    assert render_source_schema(_read(engine, ["main", "Other"]), header=header) == text
    path = tmp_path / "schema.yml"
    path.write_text(text, encoding="utf-8")
    assert load_source_schemas(path) == tables
    document = yaml.safe_load(text)
    customer = next(t for t in document["source_schemas"] if t["table"] == "Customer")
    assert set(customer) == {
        "table", "schema", "database", "columns", "primary_key", "unique_keys",
    }, "empty lists are omitted, as the derivation omits them"
    assert customer["columns"][0] == {"name": "CustomerID", "type": "integer", "nullable": False}


# --- P1: the paths SQLite cannot show, through a stub reader ---------------------------------


class _StubReader:
    """A reader that has comments on one column and cannot say anything about unique keys."""

    default_schema = "dbo"

    def schema_names(self) -> list[str]:
        return ["dbo"]

    def table_names(self, schema: str) -> list[str]:
        return ["Person"]

    def view_names(self, schema: str) -> list[str]:
        return []

    def columns(self, table: str, schema: str) -> list[ReadColumn]:
        return [
            ReadColumn("BusinessEntityID", "int", False, "Primary key for Person records."),
            ReadColumn("FirstName", "nvarchar(50)", False, None),
            ReadColumn("Demographics", "", True, "  Personal information such as\n hobbies. "),
        ]

    def primary_key(self, table: str, schema: str) -> list[str]:
        return ["BusinessEntityID"]

    def unique_keys(self, table: str, schema: str) -> list[list[str]]:
        raise NotImplementedError

    def foreign_keys(self, table: str, schema: str) -> list[ReadForeignKey]:
        return []


def test_p1_comments_verbatim_and_a_dialect_that_cannot_say_records_nothing() -> None:
    [person] = read_source_schema(_StubReader(), schemas=["dbo"], database=None)
    assert [c.comment for c in person.column_refs] == [
        "Primary key for Person records.", None, "  Personal information such as\n hobbies. ",
    ], "verbatim, whitespace kept — the mapper normalises, the reader does not"
    assert person.unique_keys == [], "NotImplementedError is 'no unique keys', not a failure"
    assert person.column_refs[2].type == ""
    assert person.database is None


def test_p1_an_unknown_type_is_empty_never_guessed() -> None:
    dialect = sa.create_engine("sqlite://").dialect
    assert InspectorReader.type_name(sqltypes.NullType(), dialect) == ""
    assert InspectorReader.type_name(sqltypes.VARCHAR(50), dialect) == "varchar(50)"


# --- P2: the command --------------------------------------------------------------------------


runner = CliRunner()


def test_p2_without_a_schema_the_command_lists_the_catalogue_and_exits_2(
    engine: sa.Engine, tmp_path: Path
) -> None:
    result = runner.invoke(
        app, ["source-schema", "--url", str(engine.url), "--out", str(tmp_path / "s.yml")]
    )
    assert result.exit_code == 2, result.output
    assert "main" in result.output and "Other" not in result.output, (
        "the schemas this connection sees (the attachment is the test's, not the URL's)"
    )
    assert not (tmp_path / "s.yml").exists()


def test_p2_a_schema_the_catalogue_lacks_exits_2(engine: sa.Engine, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["source-schema", "--url", str(engine.url), "--schema", "Sales",
              "--out", str(tmp_path / "s.yml")],
    )
    assert result.exit_code == 2, result.output
    assert "Sales" in result.output and "main" in result.output


def test_p2_without_a_url_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAULT_AGENT_SOURCE_URL", raising=False)
    result = runner.invoke(
        app, ["source-schema", "--schema", "main", "--out", str(tmp_path / "s.yml")]
    )
    assert result.exit_code == 2, result.output
    assert "VAULT_AGENT_SOURCE_URL" in result.output


def test_p2_a_missing_driver_exits_1_naming_the_driver_never_the_password(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app, ["source-schema", "--url", "mssql+pyodbc://user:s3cret@host/db",
              "--schema", "dbo", "--out", str(tmp_path / "s.yml")],
    )
    assert result.exit_code == 1, result.output
    assert "pyodbc" in result.output
    assert "s3cret" not in result.output
    assert hidden_url("mssql+pyodbc://user:s3cret@host/db") == "mssql+pyodbc://user:***@host/db"


def test_p2_the_command_writes_the_file_from_the_environment_url(
    engine: sa.Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULT_AGENT_SOURCE_URL", str(engine.url))
    out = tmp_path / "s.yml"
    result = runner.invoke(app, ["source-schema", "--schema", "main", "--out", str(out)])
    assert result.exit_code == 0, result.output
    tables = load_source_schemas(out)
    assert [t.table for t in tables] == ["Customer", "SalesOrderHeader"]
    assert out.read_text(encoding="utf-8").startswith("# read by vault-agent source-schema from ")
    assert "2 tables" in result.output


# --- P3: the DDL instrument ---------------------------------------------------------------------


def test_p3_the_instrument_renders_every_object_of_the_extract() -> None:
    from eval.adventureworks.postgres_ddl import render_ddl

    extract = json.loads(_EXTRACT.read_text(encoding="utf-8"))
    ddl = render_ddl(extract)
    counts = {
        "tables": len(re.findall(r"^CREATE TABLE ", ddl, re.M)),
        "primary keys": ddl.count("PRIMARY KEY ("),
        "unique indexes": len(re.findall(r"^CREATE UNIQUE INDEX ", ddl, re.M)),
        "foreign keys": ddl.count("FOREIGN KEY ("),
        "table comments": len(re.findall(r"^COMMENT ON TABLE ", ddl, re.M)),
        "column comments": len(re.findall(r"^COMMENT ON COLUMN ", ddl, re.M)),
        "columns": len(re.findall(r'^    "\w+" \S', ddl, re.M)),
        "schemas": len(re.findall(r"^CREATE SCHEMA ", ddl, re.M)),
    }
    assert counts == {
        "tables": 68, "primary keys": 68, "unique indexes": 55, "foreign keys": 90,
        "table comments": 66, "column comments": 440, "columns": 465, "schemas": 5,
    }
    assert '"FirstName" varchar(50) NOT NULL' in ddl, "the alias type Name resolves to its base"
    assert '"rowguid" uuid NOT NULL' in ddl
    assert '"TotalDue" text' in ddl, "a computed column is declared text (spec §4 P3)"
    assert "COMMENT ON COLUMN \"Person\".\"Person\".\"FirstName\" IS 'First name of the person.'" in ddl
    assert ddl.index("FOREIGN KEY (") > ddl.rindex("CREATE TABLE "), (
        "every foreign key after every table, so the DDL applies in one pass"
    )
