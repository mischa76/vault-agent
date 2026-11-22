"""Sanity tests for the shared state model."""
from vault_agent.state import Link, LinkHubRef, VaultAgentState


def test_state_initializes_empty() -> None:
    state = VaultAgentState()
    assert state.requirements == []
    assert state.dv_model.hubs == []
    assert state.validation_report.passed is False


# --- WP8 / ADR-0009: role-qualified link hub references ---


def test_plain_string_hubs_coerce_to_unqualified_refs() -> None:
    """A plain-string connected_hubs list normalises to unqualified LinkHubRefs."""
    link = Link(name="l", connected_hubs=["hub_a", "hub_b"], description="d")
    assert [(r.hub, r.role) for r in link.hub_refs] == [("hub_a", None), ("hub_b", None)]


def test_role_qualified_and_mixed_refs_are_accepted() -> None:
    """A role object (and a dict) coexist with plain strings; the union keeps both forms."""
    link = Link(
        name="link_transfer",
        connected_hubs=[
            "hub_account",
            LinkHubRef(hub="hub_account", role="counterparty"),
            {"hub": "hub_bank"},  # dict form also coerces
        ],
        description="d",
    )
    assert [(r.hub, r.role) for r in link.hub_refs] == [
        ("hub_account", None),
        ("hub_account", "counterparty"),
        ("hub_bank", None),
    ]


def test_hub_refs_coerces_post_construction_assignment() -> None:
    """Direct field assignment bypasses the before-validator; hub_refs re-coerces strings."""
    link = Link(name="l", connected_hubs=["hub_a", "hub_b"], description="d")
    link.connected_hubs = ["hub_a", "hub_c"]  # raw strings, no validation on assignment
    assert [r.hub for r in link.hub_refs] == ["hub_a", "hub_c"]
    assert all(r.role is None for r in link.hub_refs)


def test_resolve_driving_refs_matches_bare_and_role_qualified_entries() -> None:
    link = Link(
        name="link_transfer",
        connected_hubs=["hub_account", LinkHubRef(hub="hub_account", role="counterparty")],
        description="d",
        driving_key=["hub_account:counterparty"],
    )
    resolved = link.resolve_driving_refs()
    assert [(r.hub, r.role) for r in resolved] == [("hub_account", "counterparty")]


def test_resolve_driving_refs_drops_unmatched_entries() -> None:
    """An entry naming no connected participation is dropped (the validator reports it)."""
    link = Link(
        name="l",
        connected_hubs=["hub_a", "hub_b"],
        description="d",
        driving_key=["hub_a", "hub_ghost", "hub_b:role"],
    )
    assert [(r.hub, r.role) for r in link.resolve_driving_refs()] == [("hub_a", None)]


def test_connected_hubs_round_trip_through_model_dump() -> None:
    """model_dump emits ref dicts that re-validate to the same refs (checkpointer safety)."""
    link = Link(
        name="link_transfer",
        connected_hubs=["hub_account", LinkHubRef(hub="hub_account", role="counterparty")],
        description="d",
    )
    restored = Link.model_validate(link.model_dump())
    assert [(r.hub, r.role) for r in restored.hub_refs] == [
        ("hub_account", None),
        ("hub_account", "counterparty"),
    ]
