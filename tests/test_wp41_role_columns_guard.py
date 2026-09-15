"""WP41 guard, committed BEFORE the capability (spec §3).

Two miniatures of the shapes the five persisted AdventureWorks chains carry, through the real
proposer, modeler (stub extractor), generator and validator:

* greenfield contact: `BusinessEntityContact(BusinessEntityID → BusinessEntity, PersonID → Person,
  ContactTypeID → ContactType)`; the modeler links `hub_business_entity:organisation`,
  `hub_person:contact` (or unqualified) and `hub_contact_type`, with a satellite read from the
  same table;
* production bill of materials: `BillOfMaterials(ProductAssemblyID, ComponentID → Product.ProductID,
  UnitMeasureCode)`, `hub_product` keyed on `ProductNumber`, the link taking `hub_product` twice.

* ``test_greenfield_proposes_no_license`` — FLIPPED by WP41.
* ``test_the_contact_link_stage_demands_role_columns_and_its_satellite_is_refused`` — FLIPPED.
* ``test_an_unqualified_person_from_the_organisation_column_is_refused`` — FLIPPED.
* ``test_the_bill_of_materials_stage_demands_role_columns`` — FLIPPED.
* ``test_an_unqualified_participation_beside_a_role_of_the_same_hub_is_not_repaired`` — never.
* ``test_declined_licenses_leave_greenfield_artifacts_byte_identical`` — never.
* ``test_nothing_is_built_the_modeler_did_not_build`` — never.
"""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.staging_generator import collect_staging_specs
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import collect_link_proposals
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    Hub,
    LinkProposals,
    ParsedRequirement,
    SourceTable,
    VaultAgentState,
)


def _fk(column: str, table: str, referenced: str) -> dict[str, Any]:
    return {"columns": [column], "references_table": table, "references_columns": [referenced]}


def contact_schema(*, foreign_keys: bool = True) -> list[SourceTable]:
    def fks(*keys: dict[str, Any]) -> list[dict[str, Any]]:
        return list(keys) if foreign_keys else []

    return [
        SourceTable(table="BusinessEntity", columns=["BusinessEntityID", "ModifiedDate"]),
        SourceTable(table="Person", columns=["BusinessEntityID", "FirstName"],
                    foreign_keys=fks(_fk("BusinessEntityID", "BusinessEntity", "BusinessEntityID"))),
        SourceTable(table="ContactType", columns=["ContactTypeID", "Name"]),
        SourceTable(table="BusinessEntityContact",
                    columns=["BusinessEntityID", "PersonID", "ContactTypeID", "ModifiedDate"],
                    foreign_keys=fks(_fk("PersonID", "Person", "BusinessEntityID"),
                                     _fk("ContactTypeID", "ContactType", "ContactTypeID"),
                                     _fk("BusinessEntityID", "BusinessEntity", "BusinessEntityID"))),
    ]


def contact_payload(*, person_role: str | None = "contact") -> dict[str, Any]:
    person: dict[str, Any] = {"hub": "hub_person"}
    if person_role is not None:
        person["role"] = person_role
    return {
        "hubs": [
            {"name": "hub_business_entity", "business_key": "BusinessEntityID",
             "source_entity": "BusinessEntity", "description": "A business entity."},
            {"name": "hub_person", "business_key": "BusinessEntityID", "source_entity": "Person",
             "description": "A person."},
            {"name": "hub_contact_type", "business_key": "ContactTypeID",
             "source_entity": "ContactType", "description": "A contact type."},
        ],
        "links": [{"name": "link_business_entity_contact",
                   "connected_hubs": [{"hub": "hub_business_entity", "role": "organisation"},
                                      person, "hub_contact_type"],
                   "description": "A person is a contact of an organisation."}],
        "satellites": [
            {"name": "sat_person_details", "parent": "hub_person", "attributes": ["FirstName"],
             "description": "Names."},
            {"name": "sat_business_entity_contact_details",
             "parent": "link_business_entity_contact", "attributes": ["ModifiedDate"],
             "source_table": "BusinessEntityContact", "description": "Contact details."},
        ],
    }


def bom_schema() -> list[SourceTable]:
    return [
        SourceTable(table="Product", columns=["ProductID", "ProductNumber", "Name"]),
        SourceTable(table="UnitMeasure", columns=["UnitMeasureCode", "Name"]),
        SourceTable(table="BillOfMaterials",
                    columns=["BillOfMaterialsID", "ProductAssemblyID", "ComponentID",
                             "UnitMeasureCode", "PerAssemblyQty"],
                    foreign_keys=[_fk("ProductAssemblyID", "Product", "ProductID"),
                                  _fk("ComponentID", "Product", "ProductID"),
                                  _fk("UnitMeasureCode", "UnitMeasure", "UnitMeasureCode")]),
    ]


def bom_payload(*, assembly_role: str | None = "assembly") -> dict[str, Any]:
    assembly: dict[str, Any] = {"hub": "hub_product"}
    if assembly_role is not None:
        assembly["role"] = assembly_role
    return {
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_unit_measure", "business_key": "UnitMeasureCode",
             "source_entity": "UnitMeasure", "description": "A unit of measure."},
        ],
        "links": [{"name": "link_bill_of_materials",
                   "connected_hubs": [assembly, {"hub": "hub_product", "role": "component"},
                                      "hub_unit_measure"],
                   "description": "A component of an assembly."}],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "description": "Product attributes."},
            {"name": "sat_bill_of_materials_details", "parent": "link_bill_of_materials",
             "attributes": ["PerAssemblyQty"], "source_table": "BillOfMaterials",
             "description": "Quantities."},
        ],
    }


def greenfield_state(schemas: list[SourceTable], *, accept: bool = True) -> VaultAgentState:
    state = VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-1", text="Entities relate.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="person", field="BusinessEntityID", score=0.9,
                                            rationale="r")],
        source_schemas=schemas,
    )
    collect_link_proposals(state)
    if accept:
        apply_link_decision(state, {"accept": True})
    else:
        apply_link_decision(state, {"links": {
            f"{lic.source_table}.{lic.source_column}": False for lic in state.link_proposals.licenses
        }})
    return state


async def run_greenfield(
    payload: dict[str, Any], schemas: list[SourceTable], *, accept: bool = True
) -> VaultAgentState:
    state = greenfield_state(schemas, accept=accept)
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    state = await CodeGeneratorAgent().run(state)
    return await ValidatorAgent().run(state)


def _stage_columns(model: DVModel, name: str) -> set[str]:
    return set(collect_staging_specs(model)[name].source_columns)


def _codes(state: VaultAgentState, code: str) -> set[str]:
    return {i.construct for i in state.validation_report.issues if i.code == code}


def test_greenfield_proposes_no_license() -> None:
    state = greenfield_state(contact_schema())
    assert state.link_proposals == LinkProposals()


async def test_the_contact_link_stage_demands_role_columns_and_its_satellite_is_refused() -> None:
    state = await run_greenfield(contact_payload(), contact_schema())
    columns = _stage_columns(state.dv_model, "stg_business_entity_contact")
    assert {"ORGANISATION_BUSINESSENTITYID", "CONTACT_BUSINESSENTITYID"} <= columns
    assert "sat_business_entity_contact_details" in _codes(state, "E_SAT_KEY_NOT_IN_SOURCE")


async def test_an_unqualified_person_from_the_organisation_column_is_refused() -> None:
    state = await run_greenfield(contact_payload(person_role=None), contact_schema())
    assert "link_business_entity_contact" in _codes(state, "E_LINK_KEY_WRONG_COLUMN")


async def test_the_bill_of_materials_stage_demands_role_columns() -> None:
    state = await run_greenfield(bom_payload(), bom_schema())
    columns = _stage_columns(state.dv_model, "stg_bill_of_materials")
    assert {"ASSEMBLY_PRODUCTNUMBER", "COMPONENT_PRODUCTNUMBER"} <= columns


async def test_an_unqualified_participation_beside_a_role_of_the_same_hub_is_not_repaired() -> None:
    state = await run_greenfield(bom_payload(assembly_role=None), bom_schema())
    [link] = state.dv_model.links
    [plain] = [r for r in link.hub_refs if r.hub == "hub_product" and r.role is None]
    assert plain.key_translation is None and plain.source_key_column is None


async def test_declined_licenses_leave_greenfield_artifacts_byte_identical() -> None:
    with_fks = await run_greenfield(contact_payload(), contact_schema(), accept=False)
    without = await run_greenfield(contact_payload(), contact_schema(foreign_keys=False))
    assert with_fks.artifacts.staging_models == without.artifacts.staging_models
    assert with_fks.artifacts.dbt_models == without.artifacts.dbt_models
    assert with_fks.artifacts.automatedv_yaml == without.artifacts.automatedv_yaml


async def test_nothing_is_built_the_modeler_did_not_build() -> None:
    state = await run_greenfield(contact_payload(), contact_schema())
    assert [link.name for link in state.dv_model.links] == ["link_business_entity_contact"]
    assert {hub.name for hub in state.dv_model.hubs} == {
        "hub_business_entity", "hub_person", "hub_contact_type"
    }
    assert isinstance(state.dv_model, DVModel) and all(isinstance(h, Hub) for h in state.dv_model.hubs)
