"""WP137 — beside declared keys, an inference the declarations already answer is neither made
nor offered (C73, spec §4). Committed red before the change: P1 on SQLite through the real
inference, P2 on the proposer. The pins (`…_keeps_…`) are green before and after: what the
change must not lose. Keyless."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa

from vault_agent.key_inference import infer_keys
from vault_agent.link_proposal import propose_links
from vault_agent.state import DVModel, InferredForeignKey, SourceTable

_DDL = [
    'CREATE TABLE "Product" ("ProductID" INTEGER NOT NULL, "Name" VARCHAR(20))',
    'CREATE TABLE "ProductPhoto" ("ProductID" INTEGER NOT NULL, "PhotoID" INTEGER NOT NULL)',
    'CREATE TABLE "WorkOrder" ("WorkOrderID" INTEGER NOT NULL, "ProductID" INTEGER NOT NULL)',
    'CREATE TABLE "Routing" ("WorkOrderID" INTEGER NOT NULL, "ProductID" INTEGER NOT NULL, '
    '"Sequence" INTEGER NOT NULL)',
    'CREATE TABLE "SpecialOfferProduct" ("SpecialOfferID" INTEGER NOT NULL, '
    '"ProductID" INTEGER NOT NULL)',
    'CREATE TABLE "OrderLine" ("OrderLineID" INTEGER NOT NULL, "SpecialOfferID" INTEGER NOT NULL, '
    '"ProductID" INTEGER NOT NULL)',
]
_ROWS: dict[str, list[tuple[Any, ...]]] = {
    "Product": [(1, "A"), (2, "B"), (3, "C"), (4, "D")],
    # One photo per product: the column is unique in the data and holds every product.
    "ProductPhoto": [(1, 7), (2, 7), (3, 8), (4, 9)],
    "WorkOrder": [(1, 1), (2, 2), (3, 2)],
    "Routing": [(1, 1, 1), (2, 2, 1), (3, 2, 1), (3, 2, 2)],
    "SpecialOfferProduct": [(1, 1), (1, 2), (2, 2)],
    "OrderLine": [(1, 1, 1), (2, 1, 2), (3, 2, 2)],
}


def _fk(columns: list[str], table: str, referenced: list[str]) -> dict[str, Any]:
    return {"columns": columns, "references_table": table, "references_columns": referenced,
            "references_schema": "main"}


def _tables(*, work_order_column: str = "ProductID") -> list[SourceTable]:
    to_product = _fk(["ProductID"], "Product", ["ProductID"])
    return [
        SourceTable(table="Product", schema="main", columns=["ProductID", "Name"],
                    primary_key=["ProductID"]),
        SourceTable(table="ProductPhoto", schema="main", columns=["ProductID", "PhotoID"],
                    primary_key=["ProductID", "PhotoID"], foreign_keys=[to_product]),
        SourceTable(table="WorkOrder", schema="main", columns=["WorkOrderID", "ProductID"],
                    primary_key=["WorkOrderID"],
                    foreign_keys=[_fk([work_order_column], "Product", ["ProductID"])]),
        SourceTable(table="Routing", schema="main",
                    columns=["WorkOrderID", "ProductID", "Sequence"],
                    primary_key=["WorkOrderID", "ProductID", "Sequence"],
                    foreign_keys=[_fk(["WorkOrderID"], "WorkOrder", ["WorkOrderID"])]),
        SourceTable(table="SpecialOfferProduct", schema="main",
                    columns=["SpecialOfferID", "ProductID"],
                    primary_key=["SpecialOfferID", "ProductID"], foreign_keys=[to_product]),
        SourceTable(table="OrderLine", schema="main",
                    columns=["OrderLineID", "SpecialOfferID", "ProductID"],
                    primary_key=["OrderLineID"],
                    foreign_keys=[_fk(["SpecialOfferID", "ProductID"], "SpecialOfferProduct",
                                      ["SpecialOfferID", "ProductID"])]),
    ]


@pytest.fixture
def engine(tmp_path: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'main.db'}")
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        for table, rows in _ROWS.items():
            marks = ", ".join("?" for _ in rows[0])
            connection.exec_driver_sql(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    return engine


def _foreign(tables: list[SourceTable], name: str) -> list[InferredForeignKey]:
    [table] = [t for t in tables if t.table == name]
    assert table.inferred_keys is not None, f"{name} was read"
    return table.inferred_keys.foreign


def _pairs(keys: list[InferredForeignKey]) -> list[tuple[str, str]]:
    return [(k.columns[0], f"{k.references_table}.{k.references_columns[0]}") for k in keys]


# ── P1 the inference ────────────────────────────────────────────────────────────────────


def test_p1_a_column_with_a_declared_key_gets_no_next_best_target(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(), candidates="name")
    assert _pairs(_foreign(inferred, "WorkOrder")) == [], (
        "WorkOrder.ProductID declares its key to Product; the photo table's column that happens "
        "to hold every product is not a second key for it"
    )
    assert _pairs(_foreign(inferred, "ProductPhoto")) == []
    offer = _pairs(_foreign(inferred, "SpecialOfferProduct"))
    assert [p for p in offer if p[0] == "ProductID"] == []


def test_p1_the_declaration_is_read_by_the_normalised_column_name(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(work_order_column="productid"), candidates="name")
    assert _pairs(_foreign(inferred, "WorkOrder")) == []


def test_p1_a_declared_key_is_not_inferred_backwards(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(), candidates="name")
    assert _pairs(_foreign(inferred, "Product")) == [], (
        "ProductPhoto.ProductID → Product.ProductID is declared; that every product has one "
        "photo does not make the photo table the product's parent"
    )
    assert [p for p in _pairs(_foreign(inferred, "WorkOrder")) if p[0] == "WorkOrderID"] == []


def test_p1_the_type_tier_follows_both_rules(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(), candidates="type")
    assert [p for p in _pairs(_foreign(inferred, "WorkOrder")) if p[0] == "ProductID"] == []
    assert ("ProductID", "ProductPhoto.ProductID") not in _pairs(_foreign(inferred, "Product"))


def test_p1_keeps_the_key_the_catalogue_does_not_declare(engine: sa.Engine) -> None:
    [key] = [k for k in _foreign(infer_keys(engine, _tables(), candidates="name"), "Routing")
             if k.columns == ["ProductID"]]
    assert (key.references_table, key.references_columns, key.tied, key.wider) == (
        "Product", ["ProductID"], ["ProductPhoto.ProductID"], []
    ), "the key WP136 needs: inferred to Product, the photo table's equal domain recorded as tied"
    assert (key.rows, key.distinct, key.referenced_distinct, key.candidate) == (4, 2, 4, "name")


def test_p1_keeps_the_component_of_a_declared_composite_key(engine: sa.Engine) -> None:
    line = _pairs(_foreign(infer_keys(engine, _tables(), candidates="name"), "OrderLine"))
    assert ("ProductID", "Product.ProductID") in line, (
        "only a single-column declaration answers for its column; the direct pair of a composite "
        "key's component is declared nowhere and stays in the file"
    )


# ── P2 the proposer ─────────────────────────────────────────────────────────────────────


def _licences(tables: list[SourceTable], key: str) -> list[tuple[str, str]]:
    proposals, _ = propose_links(DVModel(), tables)
    return [(licence.provenance, licence.references_table) for licence in proposals.licenses
            if f"{licence.source_table}.{licence.source_column}".upper() == key.upper()]


def test_p2_a_component_the_declaration_reads_onward_is_offered_once(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(), candidates="name")
    assert _licences(inferred, "OrderLine.ProductID") == [("declared", "Product")], (
        "WP46 reads the composite key's component one table further to Product; the inference of "
        "the same pair is the declaration's to propose (WP99 rule 5)"
    )


def test_p2_keeps_the_inferred_licence_of_an_undeclared_key(engine: sa.Engine) -> None:
    inferred = infer_keys(engine, _tables(), candidates="name")
    assert _licences(inferred, "Routing.ProductID") == [("inferred", "Product")]
