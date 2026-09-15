"""WP37 guard, committed BEFORE the capability.

A hub-less table with two foreign keys is a link between the keys' targets. Today the proposer
knows only the near-hub shape. Two pins: the WP34/WP36 miniatures (one key each) must never
yield a relationship proposal; and the two-key miniature yields per-FK proposals only — the
second pin was flipped by the WP in its own commit (0070562 holds the pre-WP state).
"""
from __future__ import annotations

from tests.test_link_proposal import _customer, _vault
from tests.test_wp36_translation_guard import product_hub, shopping_cart_item
from vault_agent.link_proposal import proposal_key, propose_links
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


def vendor() -> SourceTable:
    """This increment's own table: at proposal time it has no hub, so its key is PENDING."""
    return SourceTable(table="Vendor", schema="Purchasing",
                       columns=["BusinessEntityID", "AccountNumber", "Name"])


def test_a_two_key_hubless_table_is_a_relationship_proposal_with_a_pending_key() -> None:
    """Flipped by WP37 in its own commit (pinned at 0070562 as: per-key proposals only)."""
    proposals, skipped = propose_links(product_and_unit_measure(), [product_vendor(), vendor()])
    assert sorted(p.category for p in proposals.proposals) == [
        "declared_fk_same_name", "declared_fk_translated"
    ]
    # Vendor is this increment's table and has no hub yet: a `no_hub_for_key` skip until WP40,
    # a key license since (flipped by WP40 in its own commit, 2026-09-15).
    assert skipped == []
    assert [proposal_key(lic) for lic in proposals.licenses] == ["ProductVendor.BusinessEntityID"]
    [rel] = proposals.relationships
    assert rel.source_table == "ProductVendor" and rel.category == "relationship_table"
    by_col = {p.referencing_column: p for p in rel.participations}
    assert by_col["ProductID"].target_hub == "hub_product"
    assert by_col["ProductID"].key_translation is not None
    assert by_col["UnitMeasureCode"].target_hub == "hub_unit_measure"
    assert by_col["BusinessEntityID"].target_hub is None  # pending
