"""WP109 — `W_UNTRACED_CONSTRUCT`: a construct of this run that cites no requirement is a
warning, unless a ratified proposal built it (C6). Committed red before the change. Keyless."""
from __future__ import annotations

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import apply_ratified_link_proposals
from vault_agent.state import (
    DVModel,
    LinkProposal,
    ParsedRequirement,
    VaultAgentState,
)

CODE = "W_UNTRACED_CONSTRUCT"


def _requirement() -> ParsedRequirement:
    return ParsedRequirement(id="REQ-001", text="Customers place orders.", category="functional")


def _model(*, cite: bool) -> DVModel:
    ids = ["REQ-001"] if cite else []
    return DVModel.model_validate({
        "hubs": [{"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
                  "description": "x", "requirement_ids": ids},
                 {"name": "hub_order", "business_key": "SalesOrderID",
                  "source_entity": "SalesOrderHeader", "description": "x",
                  "requirement_ids": ["REQ-001"]}],
        "links": [{"name": "link_order_customer", "description": "x",
                   "connected_hubs": ["hub_order", "hub_customer"], "requirement_ids": ids}],
        "satellites": [{"name": "sat_customer_details", "parent": "hub_customer",
                        "attributes": ["Name"], "description": "x", "requirement_ids": ids}],
    })


def _untraced(state: VaultAgentState) -> list[str]:
    return sorted(i.construct for i in state.validation_report.issues if i.code == CODE)


async def test_a_construct_without_requirement_ids_is_a_warning_naming_it() -> None:
    state = VaultAgentState(dv_model=_model(cite=False), requirements=[_requirement()])
    state = await ValidatorAgent().run(state)
    assert _untraced(state) == ["hub_customer", "link_order_customer", "sat_customer_details"]
    [issue] = [i for i in state.validation_report.issues
               if i.code == CODE and i.construct == "hub_customer"]
    assert issue.severity == "warning"
    assert state.validation_report.passed  # a warning, never an error


async def test_a_cited_construct_is_silent() -> None:
    state = VaultAgentState(dv_model=_model(cite=True), requirements=[_requirement()])
    state = await ValidatorAgent().run(state)
    assert _untraced(state) == []


async def test_without_parsed_requirements_there_is_nothing_to_trace_to() -> None:
    state = await ValidatorAgent().run(VaultAgentState(dv_model=_model(cite=False)))
    assert _untraced(state) == []


async def test_an_existing_vaults_constructs_are_not_this_runs() -> None:
    state = VaultAgentState(dv_model=_model(cite=False), existing_model=_model(cite=False),
                            requirements=[_requirement()])
    state = await ValidatorAgent().run(state)
    assert _untraced(state) == []


async def test_a_link_a_ratified_proposal_built_is_exempt_but_the_same_link_by_hand_is_not() -> None:
    state = VaultAgentState(requirements=[_requirement()])
    state.link_proposals.proposals.append(LinkProposal(
        source_table="SalesOrderHeader", source_column="CustomerID", target_hub="hub_customer",
        target_business_key="CustomerID", category="declared_fk_same_name", ratification_status="accepted",
    ))
    delta = DVModel.model_validate({
        "hubs": [{"name": "hub_order", "business_key": "SalesOrderID",
                  "source_entity": "SalesOrderHeader", "description": "x",
                  "requirement_ids": ["REQ-001"]},
                 {"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
                  "description": "x", "requirement_ids": ["REQ-001"]}],
        "links": [], "satellites": [],
    })
    state.dv_model = apply_ratified_link_proposals(delta, DVModel(), state)
    [applied] = state.dv_model.links
    assert applied.requirement_ids == []
    state = await ValidatorAgent().run(state)
    assert _untraced(state) == []
    # the same link emitted by the modeler without a citation is the warning's case
    by_hand = VaultAgentState(requirements=[_requirement()])
    by_hand.dv_model = state.dv_model.model_copy(deep=True)
    by_hand = await ValidatorAgent().run(by_hand)
    assert _untraced(by_hand) == [applied.name]
