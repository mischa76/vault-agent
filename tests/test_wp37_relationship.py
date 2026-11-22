"""WP37 — relationship-table links, keyless, on the ProductVendor miniature.

Spec §5: one proposal with a pending participation; ratified, the applier resolves the pending
key against the delta (with WP36 translation where the new hub is keyed on the natural key)
and builds the three-way link; a hubbed table yields no relationship link; an unresolvable
participation yields the flag and no link; staging binds the link to the table; the gates hold.
"""
from __future__ import annotations

from tests.test_wp37_relationship_guard import product_and_unit_measure, product_vendor, vendor
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.staging_generator import build_staging
from vault_agent.link_proposal import (
    apply_ratified_link_proposals,
    collect_link_proposals,
    link_source_overrides,
    pending_link_decisions,
    proposal_key,
)
from vault_agent.state import DVModel, FlagKind, Hub, VaultAgentState


def _state() -> VaultAgentState:
    state = VaultAgentState(existing_model=product_and_unit_measure(),
                            source_schemas=[product_vendor(), vendor()])
    collect_link_proposals(state)
    return state


def _vendor_hub(keyed_on: str = "AccountNumber") -> Hub:
    return Hub(name="hub_vendor", business_key=keyed_on, source_entity="vendor",
               description="A vendor, anchored on its account number.")


def _apply(state: VaultAgentState, delta: DVModel) -> DVModel:
    apply_link_decision(state, {"accept": True})
    merged = apply_ratified_link_proposals(delta, product_and_unit_measure(), state)
    state.dv_model = DVModel(
        hubs=[*product_and_unit_measure().hubs, *merged.hubs], links=merged.links
    )
    return state.dv_model


def test_the_relationship_proposal_is_pending_and_keyed_by_table() -> None:
    state = _state()
    keys = [proposal_key(p) for p in pending_link_decisions(state.link_proposals)]
    # After the per-key proposals; since WP40 the key license for the pending Vendor key follows
    # it (licenses build nothing and are listed last).
    assert keys.index("ProductVendor.*") > keys.index("ProductVendor.ProductID")
    assert keys.index("ProductVendor.BusinessEntityID") > keys.index("ProductVendor.*")


def test_a_decision_by_table_key_ratifies_or_declines_it() -> None:
    state = _state()
    apply_link_decision(state, {"links": {"ProductVendor.*": False}})
    assert state.link_proposals.relationships[0].ratification_status == "overridden"


def test_ratified_the_pending_key_resolves_against_the_delta_with_translation() -> None:
    state = _state()
    model = _apply(state, DVModel(hubs=[_vendor_hub()]))  # keyed on the NATURAL key
    [link] = [lk for lk in model.links if lk.name == "link_product_vendor"]
    hubs = sorted(ref.hub for ref in link.hub_refs)
    assert hubs == ["hub_product", "hub_unit_measure", "hub_vendor"]
    vendor_ref = next(ref for ref in link.hub_refs if ref.hub == "hub_vendor")
    assert vendor_ref.key_translation is not None  # BusinessEntityID → AccountNumber via Vendor
    assert vendor_ref.key_translation.natural_key_column == "ACCOUNTNUMBER"
    product_ref = next(ref for ref in link.hub_refs if ref.hub == "hub_product")
    assert product_ref.key_translation is not None
    assert sum(1 for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION) == 2


def test_a_surrogate_keyed_new_hub_needs_no_translation() -> None:
    state = _state()
    model = _apply(state, DVModel(hubs=[_vendor_hub(keyed_on="BusinessEntityID")]))
    vendor_ref = next(ref for lk in model.links if lk.name == "link_product_vendor"
                      for ref in lk.hub_refs if ref.hub == "hub_vendor")
    assert vendor_ref.key_translation is None and vendor_ref.source_key_column is None


def test_a_table_the_modeler_hubbed_gets_no_relationship_link() -> None:
    state = _state()
    hubbed = Hub(name="hub_product_vendor", business_key="ProductID", source_entity="pv",
                 description="the modeler hubbed the table after all")
    model = _apply(state, DVModel(hubs=[_vendor_hub(), hubbed]))
    assert not [lk for lk in model.links if lk.name == "link_product_vendor"]
    assert not [f for f in state.flags if f.kind == FlagKind.LINK_RELATIONSHIP_INCOMPLETE]


def test_an_unresolved_participation_builds_nothing_and_flags() -> None:
    state = _state()
    model = _apply(state, DVModel())  # the modeler built no hub_vendor
    assert not [lk for lk in model.links if lk.name == "link_product_vendor"]
    [flag] = [f for f in state.flags if f.kind == FlagKind.LINK_RELATIONSHIP_INCOMPLETE]
    assert flag.asset == "ProductVendor.*" and "BusinessEntityID" in flag.message


def test_staging_binds_the_relationship_link_to_its_table() -> None:
    state = _state()
    _apply(state, DVModel(hubs=[_vendor_hub()]))
    assert link_source_overrides(state)["PRODUCT_VENDOR"] == "ProductVendor"
    result = build_staging(state.dv_model, state.source_schemas,
                           source_overrides=link_source_overrides(state))
    stage = result.models["stg_product_vendor"]
    assert "ACCOUNTNUMBER" in stage and "UNITMEASURECODE" in stage
    assert not [f for f in result.flags if f.asset == "stg_product_vendor"]  # bound, not inferred
    assert any(n.startswith("stg_product_vendor_via_") for n in result.models)  # translations


async def test_the_gates_hold_for_a_ratified_relationship_link() -> None:
    from vault_agent.agents.validator import ValidatorAgent

    state = _state()
    _apply(state, DVModel(hubs=[_vendor_hub()]))
    report = (await ValidatorAgent().run(state)).validation_report
    codes = [i.code for i in report.issues if i.code.startswith("E_LINK")]
    assert codes == [], codes


def test_purely_intra_increment_tables_and_one_key_tables_yield_nothing() -> None:
    from vault_agent.link_proposal import propose_links
    from vault_agent.state import SourceTable

    only_local = SourceTable(table="Detail", schema="X", columns=["A", "B"], foreign_keys=[
        {"columns": ["A"], "references_table": "Head", "references_columns": ["A"]},
        {"columns": ["B"], "references_table": "Other", "references_columns": ["B"]},
    ])
    head = SourceTable(table="Head", schema="X", columns=["A"])
    other = SourceTable(table="Other", schema="X", columns=["B"])
    proposals, _ = propose_links(product_and_unit_measure(), [only_local, head, other])
    assert proposals.relationships == []
