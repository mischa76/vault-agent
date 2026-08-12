"""Every declared foreign key must end up somewhere nameable, at every stage (WP34).

The 2026-08-12 runs cost ~$18 and the second one's telemetry closed the PROPOSER's ledger
exactly — 7 proposed, 31 skipped, 8 unseen, 46 total. It closed so cleanly that it hid the
next stage: 7 proposals were ratified and 2 links appeared, and nothing counted the five that
vanished in between. The loss was `construct_binds_to_source_table` refusing every multi-word
CamelCase table, which was computable from the source before either run was paid for.

The lesson is not about that rule. It is that a pipeline whose output is "items surviving N
stages" needs a CONSERVATION LEDGER — each stage accounting inputs = outputs + typed losses —
or a stage with no counter looks exactly like a stage with no losses. These tests are that
ledger for the foreign-key path, so the next stage that swallows an item fails here instead of
being discovered by a run.
"""
from __future__ import annotations

from vault_agent.link_proposal import apply_ratified_link_proposals, propose_links
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    SourceTable,
    VaultAgentState,
)

# A CamelCase landscape: the shape AdventureWorks has and every SQL Server source like it.
# One table per foreign key, each referencing a hub the prior increment already built.
SOURCES = [
    SourceTable(
        table="SalesOrderHeader", schema="Sales",
        columns=["SalesOrderID", "BillToAddressID"],
        foreign_keys=[{"columns": ["BillToAddressID"], "references_table": "Address",
                       "references_columns": ["AddressID"], "references_schema": "Person"}],
    ),
    SourceTable(
        table="PersonCreditCard", schema="Sales",
        columns=["BusinessEntityID", "CreditCardID"],
        foreign_keys=[{"columns": ["BusinessEntityID"], "references_table": "Person",
                       "references_columns": ["BusinessEntityID"], "references_schema": "Person"}],
    ),
    SourceTable(
        table="Customer", schema="Sales", columns=["CustomerID", "PersonID"],
        foreign_keys=[{"columns": ["PersonID"], "references_table": "Person",
                       "references_columns": ["BusinessEntityID"], "references_schema": "Person"}],
    ),
]


def _existing() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_address", business_key="AddressID", source_entity="address",
                description="An address."),
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
        ]
    )


def _delta() -> DVModel:
    """What the modeler built for the new increment — snake_case names for CamelCase tables,
    which is what a model does and what the binder has to cope with."""
    return DVModel(
        hubs=[
            Hub(name="hub_sales_order_header", business_key="SalesOrderID",
                source_entity="sales_order_header", description="An order."),
            Hub(name="hub_person_credit_card", business_key="CreditCardID",
                source_entity="person_credit_card", description="A card."),
            Hub(name="hub_customer", business_key="CustomerID", source_entity="customer",
                description="A customer."),
        ]
    )


def test_a_multi_word_camel_case_table_reaches_its_hub() -> None:
    """The regression that cost 5 of 7 ratified proposals. `hub_sales_order_header` and
    `SalesOrderHeader` are one identifier in two spellings."""
    proposals, _ = propose_links(_existing(), SOURCES)
    state = VaultAgentState(input_documents=["r.md"])
    state.link_proposals = proposals
    for proposal in proposals.proposals:
        proposal.ratification_status = "accepted"

    delta = apply_ratified_link_proposals(_delta(), _existing(), state)

    built = {frozenset(ref.hub for ref in link.hub_refs) for link in delta.links}
    assert frozenset({"hub_sales_order_header", "hub_address"}) in built
    assert frozenset({"hub_person_credit_card", "hub_person"}) in built
    assert frozenset({"hub_customer", "hub_person"}) in built


def test_every_declared_foreign_key_is_proposed_or_skipped_with_a_reason() -> None:
    """Stage one of the ledger. A foreign key that is neither proposed nor skipped has been
    swallowed, and no count anywhere would show it."""
    declared = sum(len(table.foreign_keys) for table in SOURCES)

    proposals, skipped = propose_links(_existing(), SOURCES)

    assert len(proposals.proposals) + len(skipped) == declared
    assert all(skip.reason for skip in skipped)


def test_every_ratified_proposal_is_applied_or_flagged() -> None:
    """Stage two, the one that had no counter and lost five items. A ratified proposal either
    becomes a link of its grain or leaves a typed flag saying why not — never neither."""
    proposals, _ = propose_links(_existing(), SOURCES)
    state = VaultAgentState(input_documents=["r.md"])
    state.link_proposals = proposals
    for proposal in proposals.proposals:
        proposal.ratification_status = "accepted"
    ratified = len(state.link_proposals.ratified())

    delta = apply_ratified_link_proposals(_delta(), _existing(), state)

    applied = len(delta.links)
    flagged = len([f for f in state.flags if f.kind == FlagKind.LINK_PROPOSAL_SKIPPED])
    assert applied + flagged == ratified, (
        f"{ratified} ratified, {applied} applied, {flagged} flagged — "
        "the difference is items no counter accounts for"
    )


def test_a_proposal_whose_near_hub_was_never_modelled_is_flagged_not_dropped() -> None:
    """The ledger has to hold when the loss is legitimate too, otherwise it only proves the
    happy path. Here the modeler built nothing for the referencing table."""
    proposals, _ = propose_links(_existing(), SOURCES)
    state = VaultAgentState(input_documents=["r.md"])
    state.link_proposals = proposals
    for proposal in proposals.proposals:
        proposal.ratification_status = "accepted"

    delta = apply_ratified_link_proposals(DVModel(), _existing(), state)

    assert not delta.links
    flagged = [f for f in state.flags if f.kind == FlagKind.LINK_PROPOSAL_SKIPPED]
    assert len(flagged) == len(state.link_proposals.ratified())
