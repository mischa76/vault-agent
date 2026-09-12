"""WP36 guard, committed BEFORE the capability (ADR-0013, accepted 2026-09-12).

Two pins on the proposer, in the miniature of the four AdventureWorks cases (a hub keyed on the
natural key `ProductNumber`, a foreign key declared on the surrogate `ProductID`):

* ``test_a_surrogate_reference_to_a_natural_key_hub_is_a_translated_proposal`` — pinned at
  2b64d03 as the skip `no_hub_for_key` the proposer produced BEFORE WP36, and flipped by the WP
  in its own commit. The flip is a recorded change, not something the new tests assume.
* ``test_a_hub_keyed_on_the_surrogate_itself_is_an_ordinary_proposal`` is the counter-case the
  ADR names: when the modeler keyed the hub on the surrogate, the FK is a plain proposal and no
  translation may ever fire. This must never change.

Everything else WP36 could disturb is pinned already: the byte-identity fixtures of WP7, WP23
and WP35 (staging, greenfield tree, Databricks scaffolding) and the WP34 inertness guards.
"""
from __future__ import annotations

from vault_agent.link_proposal import propose_links
from vault_agent.state import DVModel, Hub, SourceTable


def product_hub(keyed_on: str = "ProductNumber") -> DVModel:
    return DVModel(hubs=[
        Hub(name="hub_product", business_key=keyed_on, source_entity="product",
            description="A product, anchored on its product number."),
        Hub(name="hub_product_category", business_key="Name", source_entity="product category",
            description="Prefix trap: binds ProductCategory, never Product."),
    ])


def shopping_cart_item() -> SourceTable:
    return SourceTable(
        table="ShoppingCartItem", schema="Sales",
        columns=["ShoppingCartItemID", "ShoppingCartID", "Quantity", "ProductID"],
        foreign_keys=[{
            "columns": ["ProductID"], "references_table": "Product",
            "references_columns": ["ProductID"], "references_schema": "Production",
        }],
    )


def test_a_surrogate_reference_to_a_natural_key_hub_is_a_translated_proposal() -> None:
    """Flipped by WP36 in its own commit (was: skip ``no_hub_for_key``, pinned at 2b64d03).
    The four AdventureWorks cases are exactly this shape, and the ADR decided they are
    proposals reached by a join, not skips."""
    proposals, skipped = propose_links(product_hub(), [shopping_cart_item()])
    assert skipped == []
    [p] = proposals.proposals
    assert (p.target_hub, p.category) == ("hub_product", "declared_fk_translated")
    assert p.translation is not None
    assert (p.translation.through_table, p.translation.surrogate_column,
            p.translation.natural_key_column) == ("Product", "ProductID", "PRODUCTNUMBER")


def test_a_hub_keyed_on_the_surrogate_itself_is_an_ordinary_proposal() -> None:
    proposals, skipped = propose_links(product_hub(keyed_on="ProductID"), [shopping_cart_item()])
    assert skipped == []
    [p] = proposals.proposals
    assert (p.target_hub, p.category) == ("hub_product", "declared_fk_same_name")
