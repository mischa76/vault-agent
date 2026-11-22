"""WP32: a business concept is identified by (label, entity), never by the label alone.

Keyless. The lead test is the reproduction from the spec's §1 — three reference hubs each
keyed ``Name``, which the pre-WP32 code asked about once and then bound all three to the one
answer's relation. That was a wrong-DATA defect, so it gets a test that fails without the fix.
"""
import pytest

from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.agents.source_mapper import (
    SourceMapperAgent,
    source_overrides,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Proposal,
    ProposedMapping,
    Satellite,
    SourceColumn,
    SourceTable,
    VaultAgentState,
    concept_key,
    concept_ref_matches,
    resolve_concept_ref,
    split_concept_key,
)


def _reference_hubs() -> list[Hub]:
    """AdventureWorks Person, reduced to the shape that broke: three lookup tables whose
    business key is literally the column ``Name``."""
    return [
        Hub(name="hub_phone_number_type", business_key="Name",
            source_entity="PhoneNumberType", description="A phone number type."),
        Hub(name="hub_address_type", business_key="Name",
            source_entity="AddressType", description="An address type."),
        Hub(name="hub_contact_type", business_key="Name",
            source_entity="ContactType", description="A contact type."),
    ]


def _reference_state() -> VaultAgentState:
    tables = ["PhoneNumberType", "AddressType", "ContactType"]
    return VaultAgentState(
        dv_model=DVModel(hubs=_reference_hubs()),
        source_schemas=[
            SourceTable(table=t, columns=[SourceColumn(name="Name")]) for t in tables
        ],
    )


# --- The reproduction (spec §1) -------------------------------------------------------------


def test_same_labelled_hubs_are_three_concepts_not_one() -> None:
    concepts = SourceMapperAgent._concepts(_reference_state())

    assert [(c.concept, c.entity) for c in concepts] == [
        ("Name", "PhoneNumberType"),
        ("Name", "AddressType"),
        ("Name", "ContactType"),
    ]
    assert len({c.key for c in concepts}) == 3


def test_each_hub_binds_to_its_own_relation() -> None:
    """The wrong-data half: pre-WP32 all three staging models read PhoneNumberType."""
    state = _reference_state()
    state.mappings = ProposedMapping(
        proposals=[
            Proposal(concept="Name", entity=entity, table=entity, column="Name",
                     confidence=0.95, category="exact_name")
            for entity in ("PhoneNumberType", "AddressType", "ContactType")
        ]
    )

    assert source_overrides(state) == {
        "PHONE_NUMBER_TYPE": "PhoneNumberType",
        "ADDRESS_TYPE": "AddressType",
        "CONTACT_TYPE": "ContactType",
    }


# --- The key and the matching rule ----------------------------------------------------------


@pytest.mark.parametrize(
    ("concept", "entity", "expected"),
    [
        ("Name", "AddressType", "AddressType::Name"),
        ("Name", None, "Name"),
        ("a.b", "T", "T::a.b"),          # a dot must not be confused with TABLE.COLUMN
        ("x::y", "T", "T::x::y"),        # a label containing the separator survives
    ],
)
def test_concept_key_round_trips(concept: str, entity: str | None, expected: str) -> None:
    key = concept_key(concept, entity)
    assert key == expected
    assert split_concept_key(key) == (concept, entity)


def test_resolution_is_exact_then_unambiguous() -> None:
    candidates = [("Name", "AddressType"), ("Name", "ContactType"), ("customer name", None)]

    assert resolve_concept_ref("ContactType::Name", candidates) == 1   # exact key
    assert resolve_concept_ref("customer name", candidates) == 2       # unique label
    # A qualified reference still finds an entity-less candidate (a promoted human override).
    assert resolve_concept_ref("customer::customer name", candidates) == 2
    # The whole point: an ambiguous label resolves to NOTHING, never to an arbitrary one.
    assert resolve_concept_ref("Name", candidates) is None


def test_ambiguous_label_never_prunes_a_sibling() -> None:
    assert concept_ref_matches("Name", "Name", "AddressType", label_unique=False) is False
    assert concept_ref_matches(
        "AddressType::Name", "Name", "AddressType", label_unique=False
    ) is True
    assert concept_ref_matches("Name", "Name", "AddressType", label_unique=True) is True


# --- Post-validation lookup -----------------------------------------------------------------


class _StubProposer:
    def __init__(self, decisions: dict[str, dict]) -> None:
        self.decisions = decisions
        self.payloads: list[str] = []

    async def propose(self, *, system_prompt: str, user_content: str) -> dict:
        self.payloads.append(user_content)
        return self.decisions


async def test_qualified_answers_resolve_per_entity() -> None:
    proposer = _StubProposer(
        {
            "PhoneNumberType::Name": {"decision": "map", "table": "PhoneNumberType",
                                      "column": "Name", "confidence": 0.9},
            "AddressType::Name": {"decision": "map", "table": "AddressType",
                                  "column": "Name", "confidence": 0.9},
            "ContactType::Name": {"decision": "gap", "evidence": ["no source"]},
        }
    )
    out = await SourceMapperAgent(proposer).run(_reference_state())

    assert {(p.entity, p.table) for p in out.mappings.proposals} == {
        ("PhoneNumberType", "PhoneNumberType"),
        ("AddressType", "AddressType"),
    }
    assert out.mappings.gaps == ["ContactType::Name"]
    # The key is SENT, so the model never has to compose one.
    assert '"key": "AddressType::Name"' in proposer.payloads[0]


async def test_bare_label_answer_is_honoured_only_when_unambiguous() -> None:
    """A model that ignores the key instruction must not resolve an ambiguous label — the
    honest outcome is `unresolved` for a human, never one answer applied to three concepts."""
    proposer = _StubProposer(
        {"Name": {"decision": "map", "table": "PhoneNumberType", "column": "Name"}}
    )
    out = await SourceMapperAgent(proposer).run(_reference_state())

    assert out.mappings.proposals == []
    assert sorted(out.mappings.unresolved) == [
        "AddressType::Name", "ContactType::Name", "PhoneNumberType::Name",
    ]
    assert len([f for f in out.flags if f.kind == FlagKind.MAPPING_UNRESOLVED]) == 3


async def test_unique_label_answer_still_resolves() -> None:
    """The robustness the fallback exists for: every shipped case's stub keys by label."""
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[Hub(name="hub_customer", business_key="customer id",
                      source_entity="customer", description="A customer.")]
        ),
        source_schemas=[SourceTable(table="customer", columns=[SourceColumn(name="CUST_ID")])],
    )
    proposer = _StubProposer(
        {"customer id": {"decision": "map", "table": "customer", "column": "CUST_ID"}}
    )
    out = await SourceMapperAgent(proposer).run(state)

    assert [(p.concept, p.entity, p.column) for p in out.mappings.proposals] == [
        ("customer id", "customer", "CUST_ID")
    ]


# --- HITL ratification ----------------------------------------------------------------------


def _ratifiable() -> VaultAgentState:
    state = _reference_state()
    state.mappings = ProposedMapping(
        proposals=[
            Proposal(concept="Name", entity="PhoneNumberType", table="PhoneNumberType",
                     column="Name", confidence=0.9)
        ],
        unresolved=["AddressType::Name", "ContactType::Name"],
    )
    for entity in ("AddressType", "ContactType"):
        state.flag("source_mapper", "unresolved", kind=FlagKind.MAPPING_UNRESOLVED,
                   asset=concept_key("Name", entity))
    return state


def test_qualified_override_promotes_exactly_one_concept() -> None:
    state = _ratifiable()

    apply_human_decision(state, {"mappings": {"AddressType::Name": "AddressType.Name"}})

    promoted = next(p for p in state.mappings.proposals if p.entity == "AddressType")
    assert (promoted.table, promoted.column) == ("AddressType", "Name")
    assert promoted.ratification_status == "overridden"
    # Its sibling is untouched — neither promoted nor silently cleared.
    assert state.mappings.unresolved == ["ContactType::Name"]
    assert [f.asset for f in state.flags if f.kind == FlagKind.MAPPING_UNRESOLVED] == [
        "ContactType::Name"
    ]


def test_ambiguous_bare_override_promotes_nothing_it_cannot_identify() -> None:
    """A bare "Name" cannot name one of three. It must not pick one; the entity-less proposal
    it creates is visible in the review file rather than silently rebinding a hub."""
    state = _ratifiable()

    apply_human_decision(state, {"mappings": {"Name": "AddressType.Name"}})

    # Nothing was pruned, because nothing was identified.
    assert state.mappings.unresolved == ["AddressType::Name", "ContactType::Name"]
    assert len([f for f in state.flags if f.kind == FlagKind.MAPPING_UNRESOLVED]) == 2
    # And no hub was re-bound off the ambiguous reference.
    assert "ADDRESS_TYPE" not in source_overrides(state)


def test_bare_override_of_a_unique_label_still_works() -> None:
    """Backward compatibility: every documented `--map "concept=T.C"` keeps working."""
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[Hub(name="hub_customer", business_key="customer id",
                      source_entity="customer", description="A customer.")]
        ),
        source_schemas=[SourceTable(table="customer", columns=[SourceColumn(name="CUST_ID")])],
        mappings=ProposedMapping(unresolved=["customer::customer id"]),
    )
    state.flag("source_mapper", "unresolved", kind=FlagKind.MAPPING_UNRESOLVED,
               asset="customer::customer id")

    apply_human_decision(state, {"mappings": {"customer id": "customer.CUST_ID"}})

    assert state.mappings.unresolved == []
    assert not [f for f in state.flags if f.kind == FlagKind.MAPPING_UNRESOLVED]
    # The promoted proposal carries no entity, so the binding relies on the label fallback —
    # which is exactly why source_overrides keeps one.
    assert source_overrides(state) == {"CUSTOMER": "customer"}


def test_legacy_label_entries_are_still_pruned() -> None:
    """A checkpoint written before WP32 holds bare labels; resuming it must still clear them."""
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[Hub(name="hub_customer", business_key="customer id",
                      source_entity="customer", description="A customer.")]
        ),
        mappings=ProposedMapping(unresolved=["customer id"]),  # pre-WP32 shape
    )
    state.flag("source_mapper", "unresolved", kind=FlagKind.MAPPING_UNRESOLVED,
               asset="customer id")

    apply_human_decision(state, {"mappings": {"customer::customer id": "customer.CUST_ID"}})

    assert state.mappings.unresolved == []
    assert not [f for f in state.flags if f.kind == FlagKind.MAPPING_UNRESOLVED]


def test_satellite_attributes_are_scoped_to_their_parent() -> None:
    """The same attribute label on two parents is two concepts — they can map to different
    relations, so asking once and reusing the answer would be the same defect again."""
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[
                Hub(name="hub_order", business_key="order number", source_entity="Order",
                    description="An order."),
                Hub(name="hub_store", business_key="store name", source_entity="Store",
                    description="A store."),
            ],
            satellites=[
                Satellite(name="sat_order_details", parent="hub_order",
                          attributes=["ModifiedDate"], description="Order payload."),
                Satellite(name="sat_store_details", parent="hub_store",
                          attributes=["ModifiedDate"], description="Store payload."),
            ],
        )
    )

    keys = [c.key for c in SourceMapperAgent._concepts(state)]

    assert "hub_order::ModifiedDate" in keys and "hub_store::ModifiedDate" in keys


# --- Brownfield: an already-mapped concept is not re-asked (WP33) ----------------------------


def test_existing_constructs_are_not_re_mapped_in_an_extension() -> None:
    """WP30 arm B measured gaps growing 4 → 51 → 80 → 185 → 208 across five steps: every step
    re-mapped the whole accumulated vault against only THAT step's schema, so step 1's
    concepts became fresh "gaps" forever. Same fix WP23 gave the validator's grounding."""
    existing = DVModel(
        hubs=[Hub(name="hub_person", business_key="BusinessEntityID",
                  source_entity="Person", description="A person.")],
        satellites=[Satellite(name="sat_person_details", parent="hub_person",
                              attributes=["FirstName", "LastName"], description="Names.")],
    )
    merged = DVModel(
        hubs=list(existing.hubs) + [
            Hub(name="hub_customer", business_key="AccountNumber",
                source_entity="Customer", description="A customer.")
        ],
        satellites=list(existing.satellites) + [
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["StoreID"], description="Customer payload.")
        ],
    )
    state = VaultAgentState(dv_model=merged, existing_model=existing)

    keys = [c.key for c in SourceMapperAgent._concepts(state)]

    assert keys == ["Customer::AccountNumber", "hub_customer::StoreID"]
    # …and nothing from the pre-existing increment is asked about again.
    assert not any("BusinessEntityID" in k or "FirstName" in k for k in keys)


def test_greenfield_concept_list_is_untouched_by_the_skip() -> None:
    """Inertness guard: with no existing model the work-list is exactly as before."""
    model = DVModel(
        hubs=[Hub(name="hub_person", business_key="BusinessEntityID",
                  source_entity="Person", description="A person.")],
        satellites=[Satellite(name="sat_person_details", parent="hub_person",
                              attributes=["FirstName"], description="Names.")],
    )
    keys = [c.key for c in SourceMapperAgent._concepts(VaultAgentState(dv_model=model))]

    assert keys == ["Person::BusinessEntityID", "hub_person::FirstName"]
