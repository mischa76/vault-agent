"""Guard written FIRST, 2026-09-13, from the paid run `20260913T153801752650Z`, step 4.

Attempt 1 of the purchasing modeler built `hub_vendor` beside `hub_vendor_business_entity`;
the WP37 applier resolved ProductVendor's pending Vendor participation to the latter by
key-name match and WROTE that resolution back onto the proposal. Attempt 2 followed the new
collision remedy and dropped `hub_vendor_business_entity` — and the applier, seeing the
participation as already resolved, built `link_product_vendor` to a hub no longer in the
model: `E_LINK_UNKNOWN_HUB`. Attempt 3 re-created the hub to satisfy the link, the collision
returned, the loop was exhausted. The remedy worked; the applier undid it.

Pinned here: a pending participation is resolved against THIS attempt's merged model every
time the applier runs; nothing an earlier attempt resolved survives into the next.
"""
from __future__ import annotations

from tests.test_wp37_relationship import _state, _vendor_hub
from tests.test_wp37_relationship_guard import product_and_unit_measure
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.link_proposal import apply_ratified_link_proposals
from vault_agent.state import DVModel, Hub


def _surrogate_vendor_hub() -> Hub:
    return Hub(name="hub_vendor_business_entity", business_key="BusinessEntityID",
               source_entity="Vendor", description="the vendor as a business entity")


def test_a_later_attempt_resolves_the_pending_participation_afresh() -> None:
    state = _state()
    apply_link_decision(state, {"accept": True})
    existing = product_and_unit_measure()

    # Attempt 1: the modeler hubbed both keys; key-name match lands on the surrogate hub.
    first = apply_ratified_link_proposals(
        DVModel(hubs=[_vendor_hub(), _surrogate_vendor_hub()]), existing, state
    )
    [link] = [lk for lk in first.links if lk.name == "link_product_vendor"]
    assert "hub_vendor_business_entity" in {ref.hub for ref in link.hub_refs}

    # Attempt 2: the remedy was followed, only hub_vendor (AccountNumber) remains.
    second = apply_ratified_link_proposals(DVModel(hubs=[_vendor_hub()]), existing, state)
    [link] = [lk for lk in second.links if lk.name == "link_product_vendor"]
    hubs = {ref.hub for ref in link.hub_refs}
    assert hubs == {"hub_product", "hub_unit_measure", "hub_vendor"}, hubs
    vendor_ref = next(ref for ref in link.hub_refs if ref.hub == "hub_vendor")
    assert vendor_ref.key_translation is not None  # BusinessEntityID → AccountNumber via Vendor
