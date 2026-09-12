"""WP37 guard, committed BEFORE the capability.

A hub-less table with two foreign keys is a link between the keys' targets. Today the proposer
knows only the near-hub shape. Two pins: the WP34/WP36 miniatures (one key each) must never
yield a relationship proposal; and the two-key miniature yields per-FK proposals only — the
second pin is flipped by the WP in its own commit.
"""
from __future__ import annotations

from tests.test_link_proposal import _customer, _vault
from tests.test_wp36_translation_guard import product_hub, shopping_cart_item
from vault_agent.link_proposal import propose_links
from vault_agent.state import DVModel, Hub, SourceTable


def product_and_unit_measure() -> DVModel:
    model = product_hub()
    model.hubs.append(Hub(name="hub_unit_measure", business_key="UnitMeasureCode",
                          source_entity="unit measure", description="A unit of measure."))
    return model


def product_vendor() -> SourceTable:
    """The AdventureWorks shape: three keys, one to a table of this increment (Vendor)."""
    return SourceTable(
        table="ProductVendor", schema="Purchasing",
        columns=["ProductID", "BusinessEntityID", "UnitMeasureCode", "StandardPrice"],
        foreign_keys=[
            {"columns": ["ProductID"], "references_table": "Product",
             "references_columns": ["ProductID"], "references_schema": "Production"},
            {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
             "references_columns": ["UnitMeasureCode"], "references_schema": "Production"},
            {"columns": ["BusinessEntityID"], "references_table": "Vendor",
             "references_columns": ["BusinessEntityID"], "references_schema": "Purchasing"},
        ],
    )


def test_one_key_tables_never_yield_a_relationship_proposal() -> None:
    for vault, table in ((_vault(), _customer()), (product_hub(), shopping_cart_item())):
        proposals, _ = propose_links(vault, [table])
        assert getattr(proposals, "relationships", []) == []


def test_today_a_two_key_hubless_table_yields_per_key_proposals_only() -> None:
    proposals, skipped = propose_links(product_and_unit_measure(), [product_vendor()])
    assert sorted(p.category for p in proposals.proposals) == [
        "declared_fk_same_name", "declared_fk_translated"
    ]
    assert [s.reason for s in skipped] == ["no_hub_for_key"]  # Vendor: this increment's table
    assert getattr(proposals, "relationships", []) == []
