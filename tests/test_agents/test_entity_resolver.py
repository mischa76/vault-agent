"""WP29 — entity resolution against an existing vault (spec §3, keyless).

The order follows the spec: inertness first, because everything else in this WP is only safe
if greenfield and ungrounded runs are untouched by it. Then the two properties the Phase 2
spike identified as load-bearing — the DERIVED category (the model's self-reported one was
wrong on every exact-key case) and post-validation (a resolution naming a construct that does
not exist is demoted, never applied).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from vault_agent.agents.entity_resolver import (
    EntityResolverAgent,
    merge_decisions,
    render_resolution_prompt_section,
)
from vault_agent.agents.orchestrator import (
    apply_human_decision,
    assemble_review_queue,
)
from vault_agent.state import (
    RESOLUTION_NEW,
    RESOLUTION_SAME_AS,
    RESOLUTION_UNRESOLVED,
    BusinessKeyCandidate,
    DVModel,
    EntityResolution,
    FlagKind,
    Hub,
    ResolutionProposal,
    SourceColumn,
    SourceTable,
    VaultAgentState,
    concept_key,
)


class StubProposer:
    """Returns canned per-concept answers and records how often it was called."""

    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self.answers = answers
        self.calls = 0
        self.last_payload = ""

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]:
        self.calls += 1
        self.last_payload = user_content
        return self.answers


def _existing() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
                description="the customer"),
            Hub(name="hub_account", business_key="account_number", source_entity="account",
                description="the account"),
        ]
    )


def _schema() -> list[SourceTable]:
    return [
        SourceTable(
            table="crm_contact",
            columns=[
                SourceColumn(name="customer_id", type="varchar", comment="the customer number"),
                SourceColumn(name="partner_guid", type="uuid", comment="CRM surrogate"),
            ],
        )
    ]


def _state(**kwargs: Any) -> VaultAgentState:
    state = VaultAgentState(input_documents=["r.md"], **kwargs)
    state.business_keys = [
        BusinessKeyCandidate(entity="crm_contact", field="customer_id", score=0.9, rationale="")
    ]
    return state


def _run(agent: EntityResolverAgent, state: VaultAgentState) -> VaultAgentState:
    return asyncio.run(agent.run(state))


# --- 1. Inertness, first ------------------------------------------------------------------

def test_greenfield_makes_no_call_and_changes_nothing() -> None:
    proposer = StubProposer({})
    state = _state(source_schemas=_schema())  # grounded, but no existing model

    result = _run(EntityResolverAgent(proposer), state)

    assert proposer.calls == 0
    assert result.resolutions.proposals == []
    assert result.flags == []


def test_extension_without_a_schema_is_inert() -> None:
    proposer = StubProposer({})
    state = _state(existing_model=_existing())  # extending, but ungrounded

    result = _run(EntityResolverAgent(proposer), state)

    assert proposer.calls == 0
    assert result.resolutions.proposals == []


def test_no_business_keys_means_no_call() -> None:
    proposer = StubProposer({})
    state = VaultAgentState(
        input_documents=["r.md"], existing_model=_existing(), source_schemas=_schema()
    )

    assert _run(EntityResolverAgent(proposer), state).resolutions.proposals == []
    assert proposer.calls == 0


# --- 2. The derived category (§2.3) -------------------------------------------------------

def test_category_is_derived_and_the_models_claim_is_ignored() -> None:
    """The spike's measured failure: it reported `semantic` for every case, right or wrong."""
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer(
        {key: {"resolution": "hub_customer", "category": "semantic", "confidence": 0.4}}
    )
    state = _state(existing_model=_existing(), source_schemas=_schema())

    result = _run(EntityResolverAgent(proposer), state)

    proposal = result.resolutions.proposals[0]
    assert proposal.resolution == "hub_customer"
    # customer_id normalises to hub_customer's business key: a fact, not a guess.
    assert proposal.category == "exact_key"


# --- 3. Post-validation (§2.4) ------------------------------------------------------------

def test_an_invented_construct_is_demoted_not_applied() -> None:
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer({key: {"resolution": "hub_partner_that_does_not_exist"}})
    state = _state(existing_model=_existing(), source_schemas=_schema())

    proposal = _run(EntityResolverAgent(proposer), state).resolutions.proposals[0]

    assert proposal.resolution == RESOLUTION_UNRESOLVED
    assert not proposal.is_merge
    assert any("not a construct of the existing vault" in e for e in proposal.evidence)


def test_a_same_as_target_that_does_not_exist_is_demoted() -> None:
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer(
        {key: {"resolution": RESOLUTION_SAME_AS, "same_as": "hub_nowhere"}}
    )
    state = _state(existing_model=_existing(), source_schemas=_schema())

    proposal = _run(EntityResolverAgent(proposer), state).resolutions.proposals[0]

    assert proposal.resolution == RESOLUTION_UNRESOLVED
    assert proposal.same_as is None
    assert any("same-as target" in e for e in proposal.evidence)


def test_a_missing_answer_becomes_unresolved_with_a_flag() -> None:
    state = _state(existing_model=_existing(), source_schemas=_schema())

    result = _run(EntityResolverAgent(StubProposer({})), state)

    assert result.resolutions.proposals[0].resolution == RESOLUTION_UNRESOLVED
    kinds = [f.kind for f in result.flags]
    assert FlagKind.RESOLUTION_UNRESOLVED in kinds


# --- 4. Same-as is first-class, never a merge (§2.2) ---------------------------------------

def test_same_as_is_flagged_and_is_not_a_merge() -> None:
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer(
        {key: {"resolution": RESOLUTION_SAME_AS, "same_as": "hub_customer",
               "evidence": ["asserted equivalent, different key"]}}
    )
    state = _state(existing_model=_existing(), source_schemas=_schema())

    result = _run(EntityResolverAgent(proposer), state)

    proposal = result.resolutions.proposals[0]
    assert proposal.resolution == RESOLUTION_SAME_AS
    assert proposal.same_as == "hub_customer"
    assert not proposal.is_merge, "same-as must never count as a merge"
    assert [f.kind for f in result.flags] == [FlagKind.RESOLUTION_SAME_AS]


# --- 5. Only a RATIFIED resolution steers the modeler --------------------------------------

def test_an_unratified_proposal_does_not_steer_the_modeler() -> None:
    """The safety property: a merge nobody agreed to must not reach the modeler's prompt."""
    resolutions = EntityResolution(
        proposals=[
            ResolutionProposal(concept="customer_id", resolution="hub_customer")  # proposed
        ]
    )

    assert render_resolution_prompt_section(resolutions) == ""


def test_a_ratified_merge_reaches_the_prompt_as_the_name_to_reuse() -> None:
    resolutions = EntityResolution(
        proposals=[
            ResolutionProposal(
                concept=concept_key("partner_number", "victor_partner"),
                resolution="hub_customer",
                ratification_status="accepted",
            )
        ]
    )

    section = render_resolution_prompt_section(resolutions)

    assert "hub_customer" in section
    assert "partner_number" in section
    assert "victor_partner" in section


def test_a_ratified_same_as_tells_the_modeler_to_keep_them_apart() -> None:
    resolutions = EntityResolution(
        proposals=[
            ResolutionProposal(
                concept="partner_guid",
                resolution=RESOLUTION_SAME_AS,
                same_as="hub_customer",
                ratification_status="overridden",
            )
        ]
    )

    section = render_resolution_prompt_section(resolutions)

    assert "OWN hub" in section
    assert "do not merge" in section.lower()


def test_greenfield_prompt_section_is_empty() -> None:
    assert render_resolution_prompt_section(EntityResolution()) == ""


# --- 6. Ratification round-trip (§2.5) -----------------------------------------------------

def test_resolve_override_ratifies_and_prunes_the_flag() -> None:
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer({key: {"resolution": RESOLUTION_UNRESOLVED}})
    state = _state(existing_model=_existing(), source_schemas=_schema())
    _run(EntityResolverAgent(proposer), state)
    assert any(f.kind == FlagKind.RESOLUTION_UNRESOLVED for f in state.flags)

    apply_human_decision(state, {"resolutions": {key: "hub_customer"}})

    proposal = state.resolutions.proposals[0]
    assert proposal.resolution == "hub_customer"
    assert proposal.ratification_status == "overridden"
    assert proposal.is_merge
    assert not any(f.kind == FlagKind.RESOLUTION_UNRESOLVED for f in state.flags)
    # and now it steers
    assert "hub_customer" in render_resolution_prompt_section(state.resolutions)


def test_a_human_cannot_ratify_a_construct_that_does_not_exist() -> None:
    """The typo path: the safety property applies to the human channel too."""
    key = concept_key("customer_id", "crm_contact")
    state = _state(existing_model=_existing(), source_schemas=_schema())
    _run(EntityResolverAgent(StubProposer({key: {"resolution": RESOLUTION_UNRESOLVED}})), state)

    apply_human_decision(state, {"resolutions": {key: "hub_custmoer"}})

    assert state.resolutions.proposals[0].resolution == RESOLUTION_UNRESOLVED
    assert state.resolutions.proposals[0].ratification_status == "proposed"


def test_accept_ratifies_every_still_proposed_resolution() -> None:
    key = concept_key("customer_id", "crm_contact")
    state = _state(existing_model=_existing(), source_schemas=_schema())
    _run(EntityResolverAgent(StubProposer({key: {"resolution": "hub_customer"}})), state)

    apply_human_decision(state, {"accept": True})

    assert state.resolutions.proposals[0].ratification_status == "accepted"


# --- 7. The review queue -------------------------------------------------------------------

def test_both_flag_kinds_reach_the_review_queue_without_blocking() -> None:
    state = _state(existing_model=_existing(), source_schemas=_schema())
    state.flag(
        "entity_resolver", "undecided", kind=FlagKind.RESOLUTION_UNRESOLVED, asset="a"
    )
    state.flag("entity_resolver", "same-as", kind=FlagKind.RESOLUTION_SAME_AS, asset="b")

    queue = assemble_review_queue(state)

    assert len(queue.items) == 2
    assert all(item.kind == "review_flag" for item in queue.items)
    assert {item.group for item in queue.items} == {
        "resolution-unresolved",
        "resolution-same-as",
    }
    # An unresolved concept is honest output, not a blocker (same call WP9 made for gaps).
    assert not queue.requires_signoff


# --- 8. Plumbing --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "segments,expected",
    [
        ([{"a": {"resolution": "NEW"}}], {"a": {"resolution": "NEW"}}),
        (
            [{"a": {"resolution": "NEW"}}, {"b": {"resolution": RESOLUTION_UNRESOLVED}}],
            {"a": {"resolution": "NEW"}, "b": {"resolution": RESOLUTION_UNRESOLVED}},
        ),
        # a repeat means the model answered about a concept it was not asked for: first wins
        ([{"a": {"resolution": "NEW"}}, {"a": {"resolution": "hub_x"}}],
         {"a": {"resolution": "NEW"}}),
    ],
)
def test_merge_decisions(segments: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    assert merge_decisions(segments) == expected


def test_the_payload_carries_the_inventory_the_schema_and_the_keys() -> None:
    key = concept_key("customer_id", "crm_contact")
    proposer = StubProposer({key: {"resolution": RESOLUTION_NEW}})
    state = _state(existing_model=_existing(), source_schemas=_schema())

    _run(EntityResolverAgent(proposer), state)

    payload = proposer.last_payload
    assert "hub_customer" in payload  # the inventory to resolve against
    assert "crm_contact" in payload  # the new source
    assert key in payload  # the identity the answer must be keyed by
