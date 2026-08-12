"""What the 2026-08-12 run could not say, and what the result file now records (WP34).

That run built 2 cross-domain links. Sixteen of the 46 declared foreign keys cross a schema
and eleven had their target hub already in the vault, so between nine and ten relationships
went missing between "the source declares it" and "the model carries it" — and the result file
could not distinguish *never proposed* from *proposed and declined* from *proposed and
deduplicated*. The skips existed only as sentences inside flag messages, which nothing may
branch on, and the hubs' key columns existed nowhere at all.

These pin the three counters that separate those cases, and the hub keys that make the
standing hypothesis (hubs keyed off the column the source references) falsifiable from disk.
"""
from __future__ import annotations

from eval.run import UsageTotals, model_shape, run_metrics
from vault_agent.link_proposal import propose_links
from vault_agent.state import (
    DVModel,
    Hub,
    LinkProposal,
    LinkProposals,
    SourceTable,
    VaultAgentState,
)


def _vault() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
            Hub(name="hub_product", business_key="ProductNumber", source_entity="product",
                description="A product."),
        ]
    )


def _customer_fk(references: str = "BusinessEntityID") -> SourceTable:
    return SourceTable(
        table="Customer", schema="Sales", columns=["CustomerID", "PersonID"],
        foreign_keys=[{
            "columns": ["PersonID"],
            "references_table": "Person",
            "references_columns": [references],
            "references_schema": "Person",
        }],
    )


def test_the_hub_keys_make_the_standing_hypothesis_checkable() -> None:
    """`hub_product` is keyed on ProductNumber, so a foreign key referencing ProductID cannot
    match it. That is a claim about the result file, and this is what lets an analysis test it
    without re-running anything: the column is on disk beside the hub."""
    shape = model_shape(_vault())

    # NORMALISED, because that is what `canonical_hub_key_column` returns and what the
    # proposer actually matches against. Recording the source's casing here would make the
    # file prettier and the comparison wrong in exactly the direction that matters.
    assert shape["hub_keys"] == {
        "hub_person": "BUSINESSENTITYID",
        "hub_product": "PRODUCTNUMBER",
    }
    # The list itself is untouched — archived runs are read through it.
    assert shape["hubs"] == ["hub_person", "hub_product"]


def test_a_skip_carries_its_code_into_the_proposals() -> None:
    """The skips are part of the proposer's answer, not exhaust: a run given no foreign keys
    and a run whose foreign keys all missed are indistinguishable without them."""
    proposals, _ = propose_links(_vault(), [_customer_fk(references="SomethingElseID")])

    assert not proposals.proposals
    assert [s.reason for s in proposals.skipped] == ["no_hub_for_key"]
    assert proposals.skipped[0].asset == "Customer.PersonID"


def test_the_metrics_separate_never_proposed_from_declined() -> None:
    """The three counters, on a state carrying one accepted proposal, one refused, one skip.

    This is the shape the next paid run has to answer with; a run reporting few links and an
    empty `by_status` means something entirely different from one reporting few links and
    `{"overridden": 9}`."""
    state = VaultAgentState(input_documents=["r.md"])
    proposals, _ = propose_links(_vault(), [_customer_fk(references="SomethingElseID")])
    proposals.proposals = [
        LinkProposal(source_table="Customer", source_column="PersonID",
                     target_hub="hub_person", target_business_key="BusinessEntityID",
                     category="declared_fk_renamed", ratification_status="accepted"),
        LinkProposal(source_table="Store", source_column="BusinessEntityID",
                     target_hub="hub_person", target_business_key="BusinessEntityID",
                     category="declared_fk_same_name", ratification_status="overridden"),
    ]
    state.link_proposals = proposals

    metrics = run_metrics(state, 1.0, UsageTotals())

    assert metrics["link_proposals"] == {
        "by_category": {"declared_fk_renamed": 1, "declared_fk_same_name": 1},
        "by_status": {"accepted": 1, "overridden": 1},
        "skipped": {"no_hub_for_key": 1},
    }


def test_a_greenfield_run_reports_empty_counters_not_a_missing_key() -> None:
    """The proposer does not run without an existing model. Empty counters say "it ran and
    found nothing to say"; a missing key would be indistinguishable from an older result."""
    state = VaultAgentState(input_documents=["r.md"])
    state.link_proposals = LinkProposals()

    metrics = run_metrics(state, 1.0, UsageTotals())

    assert metrics["link_proposals"] == {"by_category": {}, "by_status": {}, "skipped": {}}


def test_flags_are_counted_by_kind_and_the_total_is_left_alone() -> None:
    """`flags` stays an integer — every archived file has one, and an int and a dict cannot be
    compared. The breakdown arrives under its own key, keyed by the typed kind."""
    state = VaultAgentState(input_documents=["r.md"])
    state.flag("link_proposer", "no link proposed for A.b: reworded tomorrow",
               kind="link_proposal_skipped", asset="A.b")
    state.flag("link_proposer", "no link proposed for C.d: also reworded",
               kind="link_proposal_skipped", asset="C.d")
    state.flag("modeler", "something else entirely", kind="generation_gap")

    metrics = run_metrics(state, 1.0, UsageTotals())

    assert metrics["flags"] == 3
    assert metrics["flag_kinds"] == {"generation_gap": 1, "link_proposal_skipped": 2}
