"""WP41 — role columns from declared keys, and key licenses in greenfield, keyless (spec §4)."""
from __future__ import annotations

import json

from tests.test_agents.test_dv2_modeler import StubExtractor
from tests.test_wp40_key_license_guard import prior_vault, production_delta, production_schema
from tests.test_wp41_role_columns_guard import (
    bom_payload,
    bom_schema,
    contact_payload,
    contact_schema,
    greenfield_state,
    run_greenfield,
)
from vault_agent.agents.code_generator import CodeGeneratorAgent, _sat_staging_model
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent, _tool_schema
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.staging_generator import collect_staging_specs
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import (
    collect_link_proposals,
    pending_link_decisions,
    proposal_key,
)
from vault_agent.rules.dv2_rules import participation_key, role_names_column
from vault_agent.state import BusinessKeyCandidate, SourceTable, VaultAgentState

REPAIR_GATES = (
    "W_ROLE_BK_NOT_IN_SOURCE", "E_SAT_KEY_NOT_IN_SOURCE", "E_SAT_TRANSLATION_UNRATIFIED",
    "E_LINK_TRANSLATION_UNRATIFIED", "E_LINK_KEY_NOT_IN_SOURCE", "E_LINK_KEY_WRONG_COLUMN",
)


def _gate_issues(state: VaultAgentState) -> list[tuple[str, str]]:
    return [(i.code, i.construct) for i in state.validation_report.issues
            if i.code in REPAIR_GATES]


def _sat(state: VaultAgentState, name: str):  # type: ignore[no-untyped-def]
    [sat] = [s for s in state.dv_model.satellites if s.name == name]
    return sat


def test_a_role_names_a_column_separator_insensitively() -> None:
    assert role_names_column("component", "ComponentID")
    assert role_names_column("assembly", "ProductAssemblyID")
    assert role_names_column("bill_to", "BillToAddressID")
    assert not role_names_column("organisation", "BusinessEntityID")
    assert participation_key("hub_product", None) == "hub_product"
    assert participation_key("hub_product", "component") == "hub_product:component"


def test_greenfield_without_foreign_keys_proposes_nothing_and_never_pauses() -> None:
    state = greenfield_state(contact_schema(foreign_keys=False), accept=False)
    assert pending_link_decisions(state.link_proposals) == []
    assert not state.flags


def test_greenfield_licenses_are_pending_decisions_and_raise_no_flags() -> None:
    state = VaultAgentState(source_schemas=contact_schema())
    collect_link_proposals(state)
    assert {proposal_key(p) for p in pending_link_decisions(state.link_proposals)} == {
        "Person.BusinessEntityID", "BusinessEntityContact.PersonID",
        "BusinessEntityContact.ContactTypeID", "BusinessEntityContact.BusinessEntityID",
    }
    assert not state.flags


async def test_the_contact_link_and_its_satellite_derive_role_columns() -> None:
    state = await run_greenfield(contact_payload(), contact_schema())
    specs = collect_staging_specs(state.dv_model)
    expected = {"ORGANISATION_BUSINESSENTITYID": "BUSINESSENTITYID",
                "CONTACT_BUSINESSENTITYID": "PERSONID"}
    assert specs["stg_business_entity_contact"].derived == expected
    sat = _sat(state, "sat_business_entity_contact_details")
    assert sat.participation_aliases == {"hub_business_entity:organisation": "BusinessEntityID",
                                         "hub_person:contact": "PersonID"}
    assert specs[_sat_staging_model(sat)].derived == expected
    assert _gate_issues(state) == []


async def test_the_unqualified_person_is_repaired_and_the_organisation_keeps_its_column() -> None:
    state = await run_greenfield(contact_payload(person_role=None), contact_schema())
    spec = collect_staging_specs(state.dv_model)["stg_business_entity_contact"]
    # derived columns are computed together from the source (automate_dv 0.11.4 derive_columns):
    # the organisation reads the source BUSINESSENTITYID, the person's key column is PERSONID.
    assert spec.derived == {"ORGANISATION_BUSINESSENTITYID": "BUSINESSENTITYID",
                            "BUSINESSENTITYID": "PERSONID"}
    assert _sat(state, "sat_business_entity_contact_details").participation_aliases[
        "hub_person"] == "PersonID"
    assert _gate_issues(state) == []


async def test_two_roles_of_one_hub_translate_through_one_table_as_two_columns() -> None:
    state = await run_greenfield(bom_payload(), bom_schema())
    stage = state.artifacts.staging_models["stg_bill_of_materials"]
    view_name = stage.split("source_model: '")[1].split("'")[0]
    view = state.artifacts.staging_models[view_name]
    assert view.count("left join") == 2
    assert ".PRODUCTNUMBER as ASSEMBLY_PRODUCTNUMBER" in view
    assert ".PRODUCTNUMBER as COMPONENT_PRODUCTNUMBER" in view
    tests = state.artifacts.scaffolding[f"models/staging/{view_name}.yml"]
    assert "- name: ASSEMBLY_PRODUCTNUMBER" in tests and "- name: COMPONENT_PRODUCTNUMBER" in tests
    sat = _sat(state, "sat_bill_of_materials_details")
    assert set(sat.participation_translations) == {"hub_product:assembly", "hub_product:component"}
    assert _gate_issues(state) == []


async def test_a_role_that_names_two_columns_pairs_with_neither() -> None:
    state = await run_greenfield(bom_payload(assembly_role="id"), bom_schema())
    [link] = state.dv_model.links
    assert all(r.key_translation is None for r in link.hub_refs if r.hub == "hub_product")


async def test_a_role_column_the_relation_already_carries_is_left_alone() -> None:
    schema = contact_schema()
    contact = schema[-1]
    schema[-1] = SourceTable(table=contact.table,
                             columns=[*contact.column_names, "Organisation_BusinessEntityID"],
                             foreign_keys=contact.foreign_keys)
    state = await run_greenfield(contact_payload(), schema)
    [link] = state.dv_model.links
    [org] = [r for r in link.hub_refs if r.hub == "hub_business_entity"]
    assert org.source_key_column is None


async def test_a_hub_satellite_between_two_keys_into_its_hub_is_not_translated() -> None:
    payload = bom_payload()
    payload["satellites"].append({"name": "sat_product_bom_usage", "parent": "hub_product",
                                  "attributes": ["PerAssemblyQty"], "sat_type": "multi_active",
                                  "child_dependent_key": ["BillOfMaterialsID"],
                                  "source_table": "BillOfMaterials", "description": "Usage."})
    state = await run_greenfield(payload, bom_schema())
    assert _sat(state, "sat_product_bom_usage").key_translation is None
    assert ("E_SAT_KEY_NOT_IN_SOURCE", "sat_product_bom_usage") in _gate_issues(state)


async def test_an_extension_repairs_roles_under_its_licenses_too() -> None:
    schema = [*production_schema(), *bom_schema()[1:]]
    state = VaultAgentState(
        existing_model=prior_vault(), source_schemas=schema,
        business_keys=[BusinessKeyCandidate(entity="product", field="ProductNumber", score=0.95,
                                            rationale="r")],
    )
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    payload = production_delta(with_link=False)
    bom = bom_payload()
    payload["hubs"].append(bom["hubs"][1])
    payload["links"] = bom["links"]
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_bill_of_materials"]
    through = {str(r): r.key_translation.through_table for r in link.hub_refs
               if r.key_translation is not None}
    assert through == {"hub_product:assembly": "Product", "hub_product:component": "Product"}


def test_the_modeler_never_sees_the_participation_aliases_field() -> None:
    assert "participation_aliases" not in json.dumps(_tool_schema())
