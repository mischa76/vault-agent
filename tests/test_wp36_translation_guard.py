"""WP36 guard, committed BEFORE the capability (ADR-0013, accepted 2026-09-12).

Two pins on the proposer, in the miniature of the four AdventureWorks cases (a hub keyed on the
natural key `ProductNumber`, a foreign key declared on the surrogate `ProductID`):

* ``test_today_a_surrogate_reference_to_a_natural_key_hub_is_skipped`` records what the
  proposer does BEFORE WP36 — the skip `no_hub_for_key`. This assertion is *meant* to flip when
  the translation lands, in the same commit, with the reason in the message. It exists so the
  flip is a recorded change and not something the new tests merely assume.
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


def test_today_a_surrogate_reference_to_a_natural_key_hub_is_skipped() -> None:
    proposals, skipped = propose_links(product_hub(), [shopping_cart_item()])
    assert proposals.proposals == []
    assert [(s.asset, s.reason) for s in skipped] == [("ShoppingCartItem.ProductID", "no_hub_for_key")]


def test_a_hub_keyed_on_the_surrogate_itself_is_an_ordinary_proposal() -> None:
    proposals, skipped = propose_links(product_hub(keyed_on="ProductID"), [shopping_cart_item()])
    assert skipped == []
    [p] = proposals.proposals
    assert (p.target_hub, p.category) == ("hub_product", "declared_fk_same_name")
