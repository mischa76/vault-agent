"""WP40 guard, committed BEFORE the capability (spec §3).

The production miniature: `Product` and `Location` are declared in this increment and the
modeler builds `hub_product` (ProductNumber) and `hub_location` (Name) in the same call;
`ProductCostHistory.ProductID → Product` and `ProductInventory.ProductID/LocationID` reference
their surrogates. Five pins, through the real proposer, modeler (stub extractor), generator and
validator:

* ``test_a_key_into_a_table_of_the_same_increment_is_a_skip`` — FLIPPED by WP40.
* ``test_a_hub_satellite_from_that_table_is_refused`` — FLIPPED by WP40.
* ``test_a_link_and_its_satellite_from_a_relation_lacking_keys_demand_them`` — FLIPPED by WP40.
* ``test_nothing_creates_a_link_the_modeler_did_not_build`` — never flipped.
* ``test_a_composite_key_stays_a_skip`` — never flipped.
"""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import collect_link_proposals, propose_links
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    Hub,
    ParsedRequirement,
    Satellite,
    SourceTable,
    VaultAgentState,
)


def prior_vault() -> DVModel:
    return DVModel(
        hubs=[Hub(name="hub_person", business_key="BusinessEntityID", source_entity="Person",
                  description="A person.")],
        satellites=[Satellite(name="sat_person_details", parent="hub_person",
                              attributes=["FirstName"], description="names")],
    )


def production_schema() -> list[SourceTable]:
    return [
        SourceTable(table="Product", columns=["ProductID", "ProductNumber", "Name"]),
        SourceTable(table="Location", columns=["LocationID", "Name"]),
        SourceTable(table="ProductCostHistory",
                    columns=["ProductID", "StartDate", "StandardCost"],
                    foreign_keys=[{"columns": ["ProductID"], "references_table": "Product",
                                   "references_columns": ["ProductID"]}]),
        SourceTable(table="ProductInventory",
                    columns=["ProductID", "LocationID", "Quantity", "Shelf"],
                    foreign_keys=[
                        {"columns": ["ProductID"], "references_table": "Product",
                         "references_columns": ["ProductID"]},
                        {"columns": ["LocationID"], "references_table": "Location",
                         "references_columns": ["LocationID"]},
                    ]),
        SourceTable(table="SalesOrderDetail",
                    columns=["SalesOrderID", "SpecialOfferID", "ProductID", "OrderQty"],
                    foreign_keys=[{"columns": ["SpecialOfferID", "ProductID"],
                                   "references_table": "SpecialOfferProduct",
                                   "references_columns": ["SpecialOfferID", "ProductID"]}]),
    ]


def production_delta(*, with_link: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_location", "business_key": "Name", "source_entity": "Location",
             "description": "A location."},
        ],
        "links": [],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "description": "Product attributes."},
            {"name": "sat_product_cost_history", "parent": "hub_product",
             "attributes": ["StandardCost"], "source_table": "ProductCostHistory",
             "sat_type": "multi_active", "child_dependent_key": ["StartDate"],
             "description": "Cost history."},
        ],
    }
    if with_link:
        payload["links"].append({"name": "link_product_inventory",
                                 "connected_hubs": ["hub_product", "hub_location"],
                                 "description": "Stock of a product at a location."})
        payload["satellites"].append({"name": "sat_product_inventory_details",
                                      "parent": "link_product_inventory",
                                      "attributes": ["Quantity", "Shelf"],
                                      "source_table": "ProductInventory",
                                      "description": "Stock level."})
    return payload


def production_state() -> VaultAgentState:
    state = VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-1", text="Products have costs.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="product", field="ProductNumber", score=0.95,
                                            rationale="r")],
        existing_model=prior_vault(),
        source_schemas=production_schema(),
    )
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    return state


async def run_production(payload: dict[str, Any]) -> VaultAgentState:
    state = production_state()
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    state = await CodeGeneratorAgent().run(state)
    return await ValidatorAgent().run(state)


def test_a_key_into_a_table_of_the_same_increment_is_a_skip() -> None:
    _, skipped = propose_links(prior_vault(), production_schema())
    assert ("ProductCostHistory.ProductID", "no_hub_for_key") in [
        (s.asset, s.reason) for s in skipped
    ]


async def test_a_hub_satellite_from_that_table_is_refused() -> None:
    state = await run_production(production_delta(with_link=False))
    refused = [i.construct for i in state.validation_report.issues
               if i.code == "E_SAT_KEY_NOT_IN_SOURCE"]
    assert refused == ["sat_product_cost_history"]


async def test_a_link_and_its_satellite_from_a_relation_lacking_keys_demand_them() -> None:
    state = await run_production(production_delta())
    link_stage = state.artifacts.staging_models["stg_product_inventory"]
    assert "source_model: 'ProductInventory'" in link_stage and "PRODUCTNUMBER" in link_stage
    refused = {i.construct for i in state.validation_report.issues
               if i.code == "E_SAT_KEY_NOT_IN_SOURCE"}
    assert "sat_product_inventory_details" in refused


async def test_nothing_creates_a_link_the_modeler_did_not_build() -> None:
    state = await run_production(production_delta(with_link=False))
    assert state.dv_model.links == []


def test_a_composite_key_stays_a_skip() -> None:
    _, skipped = propose_links(prior_vault(), production_schema())
    assert ("SalesOrderDetail.SpecialOfferID,ProductID", "composite_key") in [
        (s.asset, s.reason) for s in skipped
    ]
