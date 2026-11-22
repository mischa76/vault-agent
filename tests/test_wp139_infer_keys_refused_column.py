"""WP139 — `infer-keys` leaves out the column the database refuses to count, not its table
(C76, spec §4). PostgreSQL refuses `count(distinct c)` for a type without equality (`xml`);
SQLite refuses nothing, so the refusal is injected at the cursor. Committed red before the
change; the pin (a table refused altogether) is green before and after. Keyless."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa

from vault_agent.key_inference import infer_keys
from vault_agent.state import InferredUniqueKey, SourceTable

_DDL = [
    'CREATE TABLE "Doc" ("DocID" INTEGER NOT NULL, "Title" VARCHAR(20), "Body" TEXT)',
    'CREATE TABLE "Page" ("PageID" INTEGER NOT NULL, "DocID" INTEGER NOT NULL)',
    'CREATE TABLE "Locked" ("LockedID" INTEGER NOT NULL)',
]
_ROWS: dict[str, list[tuple[Any, ...]]] = {
    "Doc": [(1, "a", "x"), (2, "b", "x"), (3, "c", "y")],
    "Page": [(1, 1), (2, 1), (3, 3)],
    "Locked": [(1,), (2,)],
}
_COLUMNS = {"Doc": ["DocID", "Title", "Body"], "Page": ["PageID", "DocID"], "Locked": ["LockedID"]}


class UndefinedFunctionError(Exception):
    """Stands for the driver's error: no equality operator for the column's type."""


@pytest.fixture
def engine(tmp_path: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'main.db'}")
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        for table, rows in _ROWS.items():
            marks = ", ".join("?" for _ in rows[0])
            connection.exec_driver_sql(f'INSERT INTO "{table}" VALUES ({marks})', rows)

    @sa.event.listens_for(engine, "before_cursor_execute")
    def refuse(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any,
               executemany: bool) -> None:
        if not statement.lstrip().upper().startswith("SELECT"):
            return
        if 'count(DISTINCT main."Doc"."Body")' in statement or 'FROM main."Locked"' in statement:
            raise sa.exc.DBAPIError(statement, parameters, UndefinedFunctionError())

    return engine


def _infer(engine: sa.Engine) -> tuple[dict[str, SourceTable], list[str]]:
    said: list[str] = []
    tables = infer_keys(
        engine,
        [SourceTable(table=name, schema="main", columns=list(columns))
         for name, columns in _COLUMNS.items()],
        candidates="name", warn=said.append,
    )
    return {t.table: t for t in tables}, said


def test_p1_the_other_columns_of_a_table_with_a_refused_column_are_read(engine: sa.Engine) -> None:
    tables, _ = _infer(engine)
    doc = tables["Doc"].inferred_keys
    assert doc is not None, "one column the database cannot count does not cost the table"
    assert doc.unique == [
        InferredUniqueKey(columns=["DocID"], rows=3), InferredUniqueKey(columns=["Title"], rows=3)
    ]
    assert doc.foreign == []


def test_p1_a_reference_into_such_a_table_is_inferred(engine: sa.Engine) -> None:
    tables, _ = _infer(engine)
    page = tables["Page"].inferred_keys
    assert page is not None
    [key] = [k for k in page.foreign if k.columns == ["DocID"]]
    assert (key.references_table, key.references_columns) == ("Doc", ["DocID"])
    assert (key.rows, key.distinct, key.referenced_distinct) == (3, 2, 3)


def test_p1_the_refused_column_is_named_and_the_table_is_not(engine: sa.Engine) -> None:
    _, said = _infer(engine)
    about_doc = [line for line in said if "Doc" in line]
    assert len(about_doc) == 1 and about_doc[0].startswith("main.Doc.Body:"), about_doc
    assert "UndefinedFunction" in about_doc[0]


def test_p1_a_table_refused_altogether_stays_named_and_without_inferences(
    engine: sa.Engine,
) -> None:
    tables, said = _infer(engine)
    assert tables["Locked"].inferred_keys is None
    assert [line for line in said if line.startswith("main.Locked:")] == [
        "main.Locked: the database refused its counts, left without inferences"
    ]
