"""WP38 guard, committed BEFORE the capability (spec §4).

The SalesPerson miniature: `hub_employee` in the existing vault is keyed on NationalIDNumber;
`SalesPerson` declares `BusinessEntityID` as a foreign key to `Employee`; a ratified
`same_as_candidate` says the sales representative is `hub_employee`. Four pins, driven through
the real modeler (stubbed extractor) and code generator:

* ``test_a_ratified_same_as_prompts_an_own_hub`` — FLIPPED by WP38 in its own commit: with the
  join declared, the prompt stops prescribing an own hub.
* ``test_a_satellite_from_the_subtype_table_demands_the_natural_key_from_it`` — FLIPPED by WP38:
  the satellite's stage then reads a translation view instead of demanding NATIONALIDNUMBER from
  a table that does not have it.
* ``test_a_same_as_without_a_declared_join_still_prompts_an_own_hub`` — never flipped: a join
  nobody declared is a guess.
* ``test_a_table_that_references_the_subtype_is_not_translated`` — never flipped: two hops are
  out of scope (spec §6).
"""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.state import (
    RESOLUTION_SAME_AS,
    BusinessKeyCandidate,
    DVModel,
    EntityResolution,
    Hub,
    ParsedRequirement,
    ResolutionProposal,
    Satellite,
    SourceTable,
    VaultAgentState,
    concept_key,
)


def existing_vault() -> DVModel:
    return DVModel(
        hubs=[Hub(name="hub_employee", business_key="NationalIDNumber", source_entity="Employee",
                  description="An employee, anchored on the national ID number.")],
        satellites=[Satellite(name="sat_employee_details", parent="hub_employee",
                              attributes=["JobTitle"], description="Employee attributes.")],
    )


def sales_person(with_fk: bool = True) -> SourceTable:
    return SourceTable(
        table="SalesPerson",
        columns=["BusinessEntityID", "TerritoryID", "SalesQuota", "Bonus"],
        foreign_keys=[{"columns": ["BusinessEntityID"], "references_table": "Employee",
                       "references_columns": ["BusinessEntityID"]}] if with_fk else [],
    )


def quota_history() -> SourceTable:
    return SourceTable(
        table="SalesPersonQuotaHistory",
        columns=["BusinessEntityID", "QuotaDate", "SalesQuota"],
        foreign_keys=[{"columns": ["BusinessEntityID"], "references_table": "SalesPerson",
                       "references_columns": ["BusinessEntityID"]}],
    )


def subtype_state(*, with_fk: bool = True) -> VaultAgentState:
    return VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-001", text="Sales representatives have quotas.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="sales representative",
                                            field="BusinessEntityID", score=0.92,
                                            rationale="SalesPerson key")],
        existing_model=existing_vault(),
        source_schemas=[sales_person(with_fk), quota_history()],
        resolutions=EntityResolution(proposals=[ResolutionProposal(
            concept=concept_key("BusinessEntityID", "sales representative"),
            resolution=RESOLUTION_SAME_AS, same_as="hub_employee",
            ratification_status="accepted",
        )]),
    )


def subtype_payload(source_table: str = "SalesPerson") -> dict[str, Any]:
    """What a modeler following the subtype-feed sentence emits: no hub, a satellite on the
    existing hub, read from the subtype table."""
    return {
        "hubs": [],
        "links": [],
        "satellites": [{
            "name": "sat_sales_person_details", "parent": "hub_employee",
            "attributes": ["SalesQuota", "Bonus"], "source_table": source_table,
            "description": "The sales-representative role of an employee.",
        }],
    }


async def _run(state: VaultAgentState, payload: dict[str, Any]) -> tuple[str, VaultAgentState]:
    stub = StubExtractor(payload)
    state = await Dv2ModelerAgent(extractor=stub).run(state)
    state = await CodeGeneratorAgent().run(state)
    return stub.calls[0][0], state


async def test_a_ratified_same_as_with_a_declared_join_prompts_satellites_on_the_hub() -> None:
    """Flipped by WP38 in its own commit (pinned at ccdb548 as: "OWN hub")."""
    prompt, _ = await _run(subtype_state(), subtype_payload())
    assert "OWN hub" not in prompt
    assert "Do not create a hub for it" in prompt
    assert "source_table: SalesPerson" in prompt


async def test_a_satellite_from_the_subtype_table_reads_the_translation_view() -> None:
    """Flipped by WP38 in its own commit (pinned at ccdb548 as: `source_model: 'SalesPerson'`,
    demanding NATIONALIDNUMBER from a table that does not have it, no view)."""
    _, state = await _run(subtype_state(), subtype_payload())
    stage = state.artifacts.staging_models["stg_sales_person_details"]
    assert "source_model: 'stg_sales_person_details_via_employee'" in stage
    assert "NATIONALIDNUMBER" in stage  # the hub key is still what the HK is hashed from
    view = state.artifacts.staging_models["stg_sales_person_details_via_employee"]
    assert "left join" in view and "r.NATIONALIDNUMBER as NATIONALIDNUMBER" in view
    assert "on t.BUSINESSENTITYID = r.BUSINESSENTITYID" in view


async def test_a_same_as_without_a_declared_join_still_prompts_an_own_hub() -> None:
    prompt, _ = await _run(subtype_state(with_fk=False), subtype_payload())
    assert "OWN hub" in prompt


async def test_a_table_that_references_the_subtype_is_not_translated() -> None:
    _, state = await _run(subtype_state(), subtype_payload("SalesPersonQuotaHistory"))
    assert not any("_via_" in name for name in state.artifacts.staging_models)
