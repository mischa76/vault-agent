"""WP128 (ADR-0013's note of 2026-11-14) — a translation over a declared key is a disclosure;
the decision per key remains for an inferred key and a homonym. Written FIRST. Keyless."""
from __future__ import annotations

from tests.test_wp36_translation import (
    _product_table,
    _ratified_state,
    product_hub,
    shopping_cart_item,
)
from vault_agent.agents.orchestrator import apply_link_decision, assemble_review_queue
from vault_agent.link_proposal import (
    apply_ratified_link_proposals,
    collect_link_proposals,
    proposal_key,
)
from vault_agent.rules.dv2_rules import translation_key
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    KeyTranslation,
    PipelineFlag,
    VaultAgentState,
)

KEY = "hub_product=Product.PRODUCTNUMBER"


def _t() -> KeyTranslation:
    return KeyTranslation(referencing_column="ProductID", through_table="Product",
                          surrogate_column="ProductID", natural_key_column="PRODUCTNUMBER")


def _state(*confirm: bool) -> VaultAgentState:
    state = VaultAgentState()
    for n, needs in enumerate(confirm):
        state.flag("link_proposer", f"link {n} translates", kind=FlagKind.LINK_TRANSLATION,
                   asset=f"Table{n}.ProductID", reason=translation_key(_t(), "hub_product"),
                   confirm=needs)
    return state


def test_translations_over_declared_keys_are_disclosures_without_a_decision() -> None:
    queue = assemble_review_queue(_state(False, False, False))
    assert queue.decisions == []
    assert [i.group for i in queue.disclosures] == ["translation:" + KEY] * 3


def test_one_translation_to_confirm_makes_the_key_one_decision() -> None:
    queue = assemble_review_queue(_state(False, True, False))
    assert [i.asset for i in queue.decisions] == [KEY]
    assert "Table1.ProductID" in queue.decisions[0].detail
    assert len(queue.disclosures) == 3  # every construct is still disclosed under its key


def test_a_translation_flag_without_a_key_is_still_a_decision() -> None:
    state = VaultAgentState()
    state.flag("link_proposer", "translates", kind=FlagKind.LINK_TRANSLATION, asset="link_a_b")
    assert [i.asset for i in assemble_review_queue(state).decisions] == ["link_a_b"]


def test_the_proposers_declared_translation_needs_no_confirmation() -> None:
    state = _ratified_state(with_product=True)
    [flag] = [f for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION]
    assert flag.confirm is False
    queue = assemble_review_queue(state)
    assert [i for i in queue.decisions if i.kind == "review_flag"] == []
    assert [i.asset for i in queue.disclosures if i.kind == "review_flag"] == [flag.asset]


def test_an_inferred_proposals_translation_is_to_confirm() -> None:
    state = VaultAgentState(existing_model=product_hub(),
                            source_schemas=[shopping_cart_item(), _product_table()])
    collect_link_proposals(state)
    for proposal in state.link_proposals.proposals:
        proposal.provenance = "inferred"
    apply_link_decision(
        state, {"links": {proposal_key(p): True for p in state.link_proposals.proposals}})
    delta = DVModel(hubs=[Hub(name="hub_shopping_cart_item", business_key="ShoppingCartItemID",
                              source_entity="shopping cart item", description="A cart line.")])
    apply_ratified_link_proposals(delta, product_hub(), state)
    [flag] = [f for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION]
    assert flag.confirm is True
    assert [i.asset for i in assemble_review_queue(state).decisions
            if i.kind == "review_flag"] == [KEY]


def test_a_flag_that_needs_no_confirmation_serialises_as_before() -> None:
    plain = PipelineFlag(agent="a", message="m")
    assert "confirm" not in plain.model_dump()
    assert PipelineFlag(agent="a", message="m", confirm=True).model_dump()["confirm"] is True
    assert PipelineFlag.model_validate(plain.model_dump()).confirm is False
