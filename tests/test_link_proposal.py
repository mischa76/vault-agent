"""WP34: the deterministic link proposer. Keyless — there is no model call to inject.

The properties under test are the ones that decide whether this pass is safe rather than
merely useful: it proposes only from a DECLARATION, it matches on the hub's CANONICAL key
column, and where it cannot answer it says so instead of picking.
"""
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.link_proposal import (
    apply_ratified_link_proposals,
    collect_link_proposals,
    link_source_overrides,
    propose_links,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Link,
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


# ── ratification and application ───────────────────────────────────────────────────────


def _proposed(state: VaultAgentState) -> VaultAgentState:
    return collect_link_proposals(state)


def _delta() -> DVModel:
    return DVModel(
        hubs=[Hub(name="hub_customer", business_key="CustomerID",
                  source_entity="customer", description="A customer.")]
    )


def test_an_unratified_proposal_is_never_applied() -> None:
    """The whole safety property in one test: proposing is not building."""
    state = _proposed(_state(_vault(), [_customer()]))
    delta = apply_ratified_link_proposals(_delta(), _vault(), state)

    assert not delta.links


def test_a_ratified_proposal_becomes_a_link_with_the_alias_set() -> None:
    state = _proposed(_state(_vault(), [_customer()]))
    apply_link_decision(state, {"links": {"Customer.PersonID": True}})
    delta = apply_ratified_link_proposals(_delta(), _vault(), state)

    assert len(delta.links) == 1
    link = delta.links[0]
    assert link.name == "link_customer_person"
    assert [ref.hub for ref in link.hub_refs] == ["hub_customer", "hub_person"]
    # §3.4: the far side carries the referencing table's own name for the hub's key.
    assert link.hub_refs[0].source_key_column is None
    assert link.hub_refs[1].source_key_column == "PersonID"


def test_a_same_named_key_gets_no_alias_because_there_is_nothing_to_rename() -> None:
    state = _proposed(_state(_vault(), [_customer(fk_column="BusinessEntityID")]))
    apply_link_decision(state, {"links": {"Customer.BusinessEntityID": True}})
    delta = apply_ratified_link_proposals(_delta(), _vault(), state)

    assert delta.links[0].hub_refs[1].source_key_column is None


def test_a_declined_proposal_is_recorded_as_overridden_rather_than_deleted() -> None:
    """A model that considered a relationship and declined it is not the same as one that
    never saw it, and the run's record should be able to tell them apart."""
    state = _proposed(_state(_vault(), [_customer()]))
    apply_link_decision(state, {"links": {"Customer.PersonID": False}})
    delta = apply_ratified_link_proposals(_delta(), _vault(), state)

    assert state.link_proposals.proposals[0].ratification_status == "overridden"
    assert not delta.links


def test_accept_ratifies_everything_still_pending() -> None:
    """The unattended path the eval chain uses — without it §6 could not be measured."""
    state = _proposed(_state(_vault(), [_customer()]))
    decided = apply_link_decision(state, {"accept": True})

    assert decided == ["Customer.PersonID"]
    assert state.link_proposals.proposals[0].ratification_status == "accepted"


def test_a_link_the_modeler_already_built_is_not_duplicated() -> None:
    """Matched on the GRAIN, not the name: the modeler's name for it is its own choice."""
    state = _proposed(_state(_vault(), [_customer()]))
    apply_link_decision(state, {"accept": True})
    delta = _delta()
    delta.links.append(
        Link(name="link_something_else_entirely",
             connected_hubs=["hub_person", "hub_customer"], description="Already there.")
    )

    result = apply_ratified_link_proposals(delta, _vault(), state)

    assert len(result.links) == 1


def test_a_ratified_proposal_whose_near_hub_was_never_modelled_is_flagged_not_applied() -> None:
    state = _proposed(_state(_vault(), [_customer()]))
    apply_link_decision(state, {"accept": True})

    delta = apply_ratified_link_proposals(DVModel(), _vault(), state)

    assert not delta.links
    assert any(
        f.kind == FlagKind.LINK_PROPOSAL_SKIPPED and "no hub was modelled" in f.message
        for f in state.flags
    )


def test_the_link_binds_its_staging_to_the_referencing_table(tmp_path: object) -> None:
    """§3.5: the proposal knows the relation, so the binding is not inferred and not flagged."""
    state = _proposed(_state(_vault(), [_customer()]))
    apply_link_decision(state, {"accept": True})
    state.dv_model = apply_ratified_link_proposals(_delta(), _vault(), state)

    assert link_source_overrides(state) == {"CUSTOMER_PERSON": "Customer"}
