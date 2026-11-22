"""WP37 §3.1 guard — a hub binds the table it was BUILT FROM, not only the table it is named after.

Measured 2026-09-12 on the paid AdventureWorks chain: the modeler emitted ``hub_purchase_order``
with ``source_entity: PurchaseOrderHeader`` and ``hub_sales_representative`` from ``SalesPerson``.
Name-only binding could not see either, so (a) the per-key applier skipped
``PurchaseOrderHeader.EmployeeID`` as "no hub was modelled", (b) the relationship rule took the
header for hub-less and built ``link_purchase_order_header`` beside the modeler's own
``link_purchase_order_vendor``, (c) ``SalesOrderHeader.SalesPersonID`` stayed unresolved though
the hub sat there. One helper, ``hub_binds_to_source_table``, answers all three.
"""
from __future__ import annotations

from tests.test_wp37_relationship_guard import product_and_unit_measure, product_vendor, vendor
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.link_proposal import (
    apply_ratified_link_proposals,
    collect_link_proposals,
    propose_links,
)
from vault_agent.rules.dv2_rules import hub_binds_to_source_table
from vault_agent.state import DVModel, FlagKind, Hub, HubSource, SourceTable, VaultAgentState


def _hub(name: str, key: str, source_entity: str) -> Hub:
    return Hub(name=name, business_key=key, source_entity=source_entity, description="d.")


def test_the_helper_binds_by_name_by_source_entity_and_by_feed() -> None:
    by_name = _hub("hub_purchase_order_header", "PurchaseOrderID", "purchase order")
    by_entity = _hub("hub_purchase_order", "PurchaseOrderID", "PurchaseOrderHeader")
    by_feed = _hub("hub_party", "PartyID", "party")
    by_feed.sources = [HubSource(source_table="PurchaseOrderHeader", business_key_column="x")]
    unrelated = _hub("hub_purchase_order", "PurchaseOrderID", "purchase order")
    for hub in (by_name, by_entity, by_feed):
        assert hub_binds_to_source_table(hub, "PurchaseOrderHeader"), hub.name
    assert not hub_binds_to_source_table(unrelated, "PurchaseOrderHeader")
    assert not hub_binds_to_source_table(by_entity, "PurchaseOrderDetail")


def _purchase_order_header() -> SourceTable:
    return SourceTable(
        table="PurchaseOrderHeader", schema="Purchasing",
        columns=["PurchaseOrderID", "EmployeeID", "VendorID", "ShipMethodID"],
        foreign_keys=[
            {"columns": ["VendorID"], "references_table": "Vendor",
             "references_columns": ["BusinessEntityID"], "references_schema": "Purchasing"},
            {"columns": ["ShipMethodID"], "references_table": "ShipMethod",
             "references_columns": ["ShipMethodID"], "references_schema": "Purchasing"},
        ],
    )


def _vault_with_ship_method() -> DVModel:
    model = product_and_unit_measure()
    model.hubs.append(_hub("hub_ship_method", "ShipMethodID", "ShipMethod"))
    return model


def test_a_table_hubbed_under_another_name_gets_no_relationship_link() -> None:
    """The modeler's hub is named after the concept, the table after the record: same table."""
    state = VaultAgentState(existing_model=_vault_with_ship_method(),
                            source_schemas=[_purchase_order_header(), vendor()])
    collect_link_proposals(state)
    assert [r.source_table for r in state.link_proposals.relationships] == ["PurchaseOrderHeader"]
    apply_link_decision(state, {"accept": True})
    delta = DVModel(hubs=[_hub("hub_purchase_order", "PurchaseOrderID", "PurchaseOrderHeader"),
                          _hub("hub_vendor", "AccountNumber", "Vendor")])
    merged = apply_ratified_link_proposals(delta, _vault_with_ship_method(), state)
    # The per-key path covers a hubbed table; no link_purchase_order_header beside it.
    assert [lk.name for lk in merged.links] == ["link_purchase_order_ship_method"]
    assert not [f for f in state.flags if f.kind == FlagKind.LINK_RELATIONSHIP_INCOMPLETE]


def test_the_per_key_applier_finds_the_near_hub_by_source_entity() -> None:
    state = VaultAgentState(existing_model=_vault_with_ship_method(),
                            source_schemas=[_purchase_order_header(), vendor()])
    collect_link_proposals(state)
    [ship] = [p for p in state.link_proposals.proposals if p.source_column == "ShipMethodID"]
    assert ship.target_hub == "hub_ship_method"
    apply_link_decision(state, {"accept": True})
    delta = DVModel(hubs=[_hub("hub_purchase_order", "PurchaseOrderID", "PurchaseOrderHeader")])
    merged = apply_ratified_link_proposals(delta, _vault_with_ship_method(), state)
    assert [lk.name for lk in merged.links] == ["link_purchase_order_ship_method"]
    assert not [
        f for f in state.flags
        if f.kind == FlagKind.LINK_PROPOSAL_SKIPPED and f.asset.endswith("ShipMethodID")
    ]  # the one skip left is the proposer's own, for the pending Vendor key


def test_a_pending_participation_resolves_to_a_hub_named_after_the_concept() -> None:
    """SalesOrderHeader.SalesPersonID → SalesPerson, hubbed as hub_sales_representative; several
    hubs share the key BusinessEntityID, and only the source entity singles this one out."""
    existing = product_and_unit_measure()
    existing.hubs.append(_hub("hub_person", "BusinessEntityID", "Person"))
    existing.hubs.append(_hub("hub_business_entity", "BusinessEntityID", "BusinessEntity"))
    # Two hubs keyed BusinessEntityID make the Vendor key ambiguous at proposal time (a
    # SINGLE such hub is taken by WP34 tier 1 without asking which table it came from).
    proposals, _ = propose_links(existing, [product_vendor(), vendor()])
    state = VaultAgentState(existing_model=existing, source_schemas=[product_vendor(), vendor()])
    state.link_proposals = proposals
    apply_link_decision(state, {"accept": True})
    delta = DVModel(hubs=[_hub("hub_supplier", "BusinessEntityID", "Vendor")])
    merged = apply_ratified_link_proposals(delta, existing, state)
    [link] = [lk for lk in merged.links if lk.name == "link_product_vendor"]
    assert "hub_supplier" in {ref.hub for ref in link.hub_refs}
