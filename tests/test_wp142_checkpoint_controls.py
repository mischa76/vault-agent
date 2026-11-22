"""WP142 — the checkpoint's decision controls (C51, spec §4 G5): what the Review perspective
needs to offer an entity resolution's answers in words reaches it as fields — what was proposed,
the same-as candidate, and the hubs of the vault being extended (the only constructs the applier
takes as an answer). Committed red before the change. Keyless."""
from __future__ import annotations

from vault_agent.state import (
    DVModel,
    EntityResolution,
    Hub,
    ResolutionProposal,
    VaultAgentState,
)
from vault_agent.ui.runs import _existing_hubs, _pending_resolutions


def _hub(name: str) -> Hub:
    return Hub(name=name, business_key="id", source_entity=name.removeprefix("hub_"),
               description="")


def _state() -> VaultAgentState:
    return VaultAgentState(
        existing_model=DVModel(hubs=[_hub("hub_vendor"), _hub("hub_business_entity")]),
        resolutions=EntityResolution(proposals=[
            ResolutionProposal(concept="employee::businessentityid",
                               resolution="hub_business_entity", category="exact_key",
                               confidence=0.9),
            ResolutionProposal(concept="contact::contactid", resolution="same_as_candidate",
                               same_as="hub_vendor", confidence=0.7),
            ResolutionProposal(concept="shift::shiftid", resolution="NEW"),
        ]),
    )


def test_g5_a_pending_resolution_says_what_was_proposed_as_fields() -> None:
    pending = {entry["concept"]: entry for entry in _pending_resolutions(_state())}
    assert set(pending) == {"employee::businessentityid", "contact::contactid"}
    assert (pending["employee::businessentityid"]["proposed"],
            pending["employee::businessentityid"]["same_as"]) == ("hub_business_entity", None)
    assert (pending["contact::contactid"]["proposed"],
            pending["contact::contactid"]["same_as"]) == ("same_as_candidate", "hub_vendor")


def test_g5_the_hubs_of_the_existing_vault_are_the_answers_by_name() -> None:
    assert _existing_hubs(_state()) == ["hub_business_entity", "hub_vendor"]
    assert _existing_hubs(VaultAgentState()) == []
