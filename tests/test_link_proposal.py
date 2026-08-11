"""WP34: the deterministic link proposer. Keyless — there is no model call to inject.

The properties under test are the ones that decide whether this pass is safe rather than
merely useful: it proposes only from a DECLARATION, it matches on the hub's CANONICAL key
column, and where it cannot answer it says so instead of picking.
"""
from vault_agent.link_proposal import collect_link_proposals, propose_links
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    LinkProposals,
    SourceTable,
    VaultAgentState,
)


def _vault() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
        ]
    )


def _customer(fk_column: str = "PersonID", references: str = "BusinessEntityID",
              *, composite: bool = False) -> SourceTable:
    columns = ["CustomerID", fk_column, "AccountNumber"]
    fk = {
        "columns": [fk_column] + (["StoreID"] if composite else []),
        "references_table": "Person",
        "references_columns": [references] + (["OtherID"] if composite else []),
        "references_schema": "Person",
    }
    return SourceTable(table="Customer", schema="Sales", columns=columns, foreign_keys=[fk])


# ── what it proposes ───────────────────────────────────────────────────────────────────


def test_a_declared_foreign_key_to_an_existing_hub_becomes_a_proposal() -> None:
    proposals, skipped = propose_links(_vault(), [_customer()])

    assert not skipped
    assert len(proposals.proposals) == 1
    proposal = proposals.proposals[0]
    assert proposal.source_table == "Customer"
    assert proposal.source_column == "PersonID"
    assert proposal.target_hub == "hub_person"
    # The CANONICAL staging column name, not the label: that is what staging hashes from.
    assert proposal.target_business_key == "BUSINESSENTITYID"
    # Nothing is ratified by construction — the checkpoint decides, not this pass.
    assert proposal.ratification_status == "proposed"


def test_a_renamed_referencing_column_is_categorised_and_says_it_needs_an_alias() -> None:
    """§3.4: Sales.Customer.PersonID -> Person.BusinessEntityID, the motivating case."""
    proposals, _ = propose_links(_vault(), [_customer()])
    proposal = proposals.proposals[0]

    assert proposal.category == "declared_fk_renamed"
    assert proposal.needs_alias
    assert any("alias" in line for line in proposal.evidence)


def test_a_same_named_referencing_column_needs_no_alias() -> None:
    proposals, _ = propose_links(
        _vault(), [_customer(fk_column="BusinessEntityID")]
    )
    proposal = proposals.proposals[0]

    assert proposal.category == "declared_fk_same_name"
    assert not proposal.needs_alias
    assert not any("alias" in line for line in proposal.evidence)


def test_the_evidence_names_the_declaration_rather_than_asserting_a_relationship() -> None:
    proposals, _ = propose_links(_vault(), [_customer()])

    joined = " ".join(proposals.proposals[0].evidence)
    assert "declared foreign key" in joined
    assert "Customer.PersonID references Person.BusinessEntityID" in joined


def test_the_target_is_matched_on_the_hubs_canonical_key_column() -> None:
    """WP24: a multi-source hub's canonical key is not its business-key label.

    The join is made of the canonical column, so matching the label instead can be right
    about the concept and wrong about the data — the one defect class here that produces
    wrong rows rather than a wrong shape.
    """
    hub = Hub(
        name="hub_person", business_key="person_label", source_entity="person",
        description="A person.",
        sources=[
            HubSource(source_table="Person", business_key_column="BusinessEntityID"),
            HubSource(source_table="Contact", business_key_column="BusinessEntityID"),
        ],
    )
    proposals, skipped = propose_links(DVModel(hubs=[hub]), [_customer()])

    assert not skipped, "the canonical key column was not consulted"
    # Matched and reported through the helper: the LABEL is 'person_label', and a proposer
    # that read it instead would have found no hub at all for a foreign key that plainly
    # points at one.
    assert proposals.proposals[0].target_business_key == "BUSINESSENTITYID"


# ── what it refuses to answer ──────────────────────────────────────────────────────────


def test_a_composite_foreign_key_is_skipped_with_a_reason_and_never_guessed() -> None:
    """No composite FK exists in AdventureWorks (46 constraints, 46 column pairs), so this
    path has no case behind it and needs a unit test — recorded in docs/log.md."""
    proposals, skipped = propose_links(_vault(), [_customer(composite=True)])

    assert not proposals.proposals
    assert len(skipped) == 1
    asset, reason = skipped[0]
    assert asset == "Customer.PersonID,StoreID"
    assert "composite" in reason


def test_a_foreign_key_pointing_at_no_existing_hub_is_skipped() -> None:
    proposals, skipped = propose_links(
        _vault(), [_customer(references="SomethingElseID")]
    )

    assert not proposals.proposals
    assert "no existing hub is keyed on" in skipped[0][1]


def test_an_ambiguous_target_is_skipped_rather_than_picked() -> None:
    """Two hubs on the same key and a referenced table that singles out neither."""
    vault = DVModel(
        hubs=[
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
            Hub(name="hub_party", business_key="BusinessEntityID", source_entity="party",
                description="A party."),
        ]
    )
    # The referenced TABLE matches neither hub base, so there is nothing to break the tie.
    ambiguous = SourceTable(
        table="Customer", schema="Sales", columns=["CustomerID", "PersonID"],
        foreign_keys=[{
            "columns": ["PersonID"],
            "references_table": "BusinessEntity",
            "references_columns": ["BusinessEntityID"],
            "references_schema": "Person",
        }],
    )
    proposals, skipped = propose_links(vault, [ambiguous])

    assert not proposals.proposals
    assert "does not single one out" in skipped[0][1]
    assert "hub_party, hub_person" in skipped[0][1]


def test_the_referenced_table_breaks_a_tie_when_it_can() -> None:
    vault = DVModel(
        hubs=[
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
            Hub(name="hub_party", business_key="BusinessEntityID", source_entity="party",
                description="A party."),
        ]
    )
    proposals, skipped = propose_links(vault, [_customer()])

    assert not skipped
    assert proposals.proposals[0].target_hub == "hub_person"


# ── inertness ──────────────────────────────────────────────────────────────────────────


def _state(existing: DVModel | None, schemas: list[SourceTable]) -> VaultAgentState:
    state = VaultAgentState(document_path="req.md")
    state.existing_model = existing
    state.source_schemas = schemas
    return state


def test_greenfield_proposes_nothing() -> None:
    state = collect_link_proposals(_state(None, [_customer()]))

    assert state.link_proposals == LinkProposals()
    assert not state.flags


def test_an_ungrounded_extension_proposes_nothing() -> None:
    state = collect_link_proposals(_state(_vault(), []))

    assert state.link_proposals == LinkProposals()
    assert not state.flags


def test_a_schema_without_declared_foreign_keys_proposes_nothing_and_flags_nothing() -> None:
    plain = SourceTable(table="Customer", schema="Sales", columns=["CustomerID", "PersonID"])
    state = collect_link_proposals(_state(_vault(), [plain]))

    assert not state.link_proposals.proposals
    assert not state.flags


def test_a_skip_raises_a_typed_flag_consumers_can_branch_on() -> None:
    state = collect_link_proposals(_state(_vault(), [_customer(composite=True)]))

    assert [f.kind for f in state.flags] == [FlagKind.LINK_PROPOSAL_SKIPPED]
    assert state.flags[0].asset == "Customer.PersonID,StoreID"
    assert state.flags[0].severity == "advisory"


def test_the_node_is_idempotent_because_the_checkpoint_re_executes_on_resume() -> None:
    state = collect_link_proposals(_state(_vault(), [_customer()]))
    once = state.link_proposals.model_copy(deep=True)

    state = collect_link_proposals(state)

    assert state.link_proposals == once
