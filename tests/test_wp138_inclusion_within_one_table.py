"""WP138 — the inclusion check within one table (C75, spec §4). The anti-join was built from
two columns of one table object and rendered without a reference to the outer row: it asked
whether ANY row carries the same value in both columns. Committed red before the change; the
pin across two tables is green before and after. Keyless, SQLite through the real inference."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa

from vault_agent.key_inference import infer_keys
from vault_agent.state import InferredForeignKey, SourceTable

_DDL = [
    'CREATE TABLE "Item" ("ItemID" INTEGER NOT NULL, "Quantity" INTEGER NOT NULL)',
    'CREATE TABLE "Category" ("CategoryID" INTEGER NOT NULL, "ParentCategoryID" INTEGER)',
    'CREATE TABLE "Node" ("NodeID" INTEGER NOT NULL, "ParentNodeID" INTEGER)',
    'CREATE TABLE "Product" ("ProductID" INTEGER NOT NULL)',
    'CREATE TABLE "Line" ("LineID" INTEGER NOT NULL, "ProductID" INTEGER NOT NULL)',
]
_ROWS: dict[str, list[tuple[Any, ...]]] = {
    # Item 4 has quantity 4; items 2 and 5 are no quantity.
    "Item": [(2, 3), (4, 4), (5, 7)],
    # A hierarchy: one root, no row its own parent.
    "Category": [(1, None), (2, 1), (3, 1), (4, 2)],
    # A root that is its own parent, and a parent that does not exist.
    "Node": [(1, 1), (2, 1), (3, 9)],
    "Product": [(1,), (2,), (3,)],
    "Line": [(1, 2), (2, 3), (3, 2)],
}
_COLUMNS = {
    "Item": ["ItemID", "Quantity"],
    "Category": ["CategoryID", "ParentCategoryID"],
    "Node": ["NodeID", "ParentNodeID"],
    "Product": ["ProductID"],
    "Line": ["LineID", "ProductID"],
}


@pytest.fixture
def inferred(tmp_path: Path) -> dict[str, list[InferredForeignKey]]:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'main.db'}")
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        for table, rows in _ROWS.items():
            marks = ", ".join("?" for _ in rows[0])
            connection.exec_driver_sql(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    tables = infer_keys(
        engine,
        [SourceTable(table=name, schema="main", columns=list(columns))
         for name, columns in _COLUMNS.items()],
        candidates="name",
    )
    found = {}
    for table in tables:
        assert table.inferred_keys is not None, f"{table.table} was read"
        found[table.table] = table.inferred_keys.foreign
    return found


def _pairs(keys: list[InferredForeignKey]) -> list[tuple[str, str]]:
    return [(k.columns[0], f"{k.references_table}.{k.references_columns[0]}") for k in keys]


def test_p1_one_row_with_both_columns_equal_is_not_an_inclusion(
    inferred: dict[str, list[InferredForeignKey]],
) -> None:
    assert _pairs(inferred["Item"]) == [], (
        "items 2 and 5 occur in no quantity; that item 4 has quantity 4 made the old statement's "
        "subquery true for every row"
    )


def test_p1_a_reference_into_the_own_table_is_inferred_where_the_data_holds_it(
    inferred: dict[str, list[InferredForeignKey]],
) -> None:
    [key] = inferred["Category"]
    assert (key.columns, key.references_table, key.references_columns) == (
        ["ParentCategoryID"], "Category", ["CategoryID"]
    ), "every parent is a category; no row is its own parent, which the old statement required"
    assert (key.rows, key.distinct, key.referenced_distinct, key.candidate) == (3, 2, 4, "name")
    assert (key.tied, key.wider) == ([], [])


def test_p1_a_parent_that_does_not_exist_breaks_the_inclusion_within_one_table(
    inferred: dict[str, list[InferredForeignKey]],
) -> None:
    assert _pairs(inferred["Node"]) == [], (
        "parent 9 is no node; the root being its own parent must not hide that"
    )


def test_p1_keeps_the_inclusion_across_two_tables(
    inferred: dict[str, list[InferredForeignKey]],
) -> None:
    [key] = inferred["Line"]
    assert _pairs([key]) == [("ProductID", "Product.ProductID")]
    assert (key.rows, key.distinct, key.referenced_distinct) == (3, 2, 3)
    assert _pairs(inferred["Product"]) == []
