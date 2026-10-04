"""WP46 — composite foreign keys read per component; a remedy with memory for the satellite
key gate (spec §3). Committed before the change, failing.

The shapes are the two red satellites of the paid chain `20261004T013339024833Z`:
``SalesOrderDetail`` (composite key into ``SpecialOfferProduct``, whose components have onward
keys) and ``WorkOrderRouting`` (no key into ``Product`` at all).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor
from vault_agent import llm
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import collect_link_proposals, propose_links, proposal_key
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    FlagKind,
    Hub,
    Link,
    ParsedRequirement,
    RetiredConstruct,
    Satellite,
    SourceTable,
    VaultAgentState,
)

# --- the sales shape ----------------------------------------------------------------------


def _vault() -> DVModel:
    return DVModel(hubs=[
        Hub(name="hub_product", business_key="ProductNumber", source_entity="Product",
            description="A product, keyed on its number."),
        Hub(name="hub_sales_order", business_key="SalesOrderNumber",
            source_entity="SalesOrderHeader", description="A sales order."),
    ])


def _sales_schema(*, onward: tuple[str, ...] = ("ProductID", "SpecialOfferID"),
                  declare_middle: bool = True) -> list[SourceTable]:
    middle_keys = []
    if "ProductID" in onward:
        middle_keys.append({"columns": ["ProductID"], "references_table": "Product",
                            "references_columns": ["ProductID"]})
    if "SpecialOfferID" in onward:
        middle_keys.append({"columns": ["SpecialOfferID"], "references_table": "SpecialOffer",
                            "references_columns": ["SpecialOfferID"]})
    tables = [
        SourceTable(table="Product", columns=["ProductID", "Name", "ProductNumber"]),
        SourceTable(table="SalesOrderHeader", columns=["SalesOrderID", "SalesOrderNumber"]),
        SourceTable(table="SpecialOffer", columns=["SpecialOfferID", "Description"]),
        SourceTable(
            table="SalesOrderDetail",
            columns=["SalesOrderID", "SalesOrderDetailID", "ProductID", "SpecialOfferID",
                     "OrderQty"],
            foreign_keys=[
                {"columns": ["SalesOrderID"], "references_table": "SalesOrderHeader",
                 "references_columns": ["SalesOrderID"]},
                {"columns": ["SpecialOfferID", "ProductID"],
                 "references_table": "SpecialOfferProduct",
                 "references_columns": ["SpecialOfferID", "ProductID"]},
            ],
        ),
    ]
    if declare_middle:
        tables.append(SourceTable(table="SpecialOfferProduct",
                                  columns=["SpecialOfferID", "ProductID", "ModifiedDate"],
                                  foreign_keys=middle_keys))
    return tables


# --- Guard 1: the proposer reads the composite key per component ---------------------------


def test_both_components_resolve_one_table_further_and_nothing_is_skipped() -> None:
    proposals, skipped = propose_links(_vault(), _sales_schema())

    [product] = [p for p in proposals.proposals if p.source_table == "SalesOrderDetail"]
    assert product.source_column == "ProductID" and product.target_hub == "hub_product"
    assert product.category == "declared_fk_translated"
    assert product.translation is not None
    assert product.translation.through_table == "Product"
    assert product.translation.natural_key_column == "PRODUCTNUMBER"
    assert any("component" in line for line in product.evidence)

    assert "SalesOrderDetail.SpecialOfferID" in [proposal_key(lic) for lic in proposals.licenses]
    assert not [s for s in skipped if s.reason == "composite_key"]


def test_a_component_without_an_onward_key_stays_a_typed_skip_naming_it() -> None:
    proposals, skipped = propose_links(_vault(), _sales_schema(onward=("ProductID",)))

    assert [p.source_column for p in proposals.proposals if p.source_table == "SalesOrderDetail"] == [
        "ProductID"
    ]
    [skip] = [s for s in skipped if s.reason == "composite_key"]
    assert skip.asset == "SalesOrderDetail.SpecialOfferID"
    assert "ProductID" not in skip.asset


def test_an_undeclared_middle_table_keeps_the_whole_key_a_skip() -> None:
    proposals, skipped = propose_links(_vault(), _sales_schema(declare_middle=False))
    assert not [p for p in proposals.proposals if p.source_table == "SalesOrderDetail"]
    [skip] = [s for s in skipped if s.reason == "composite_key"]
    assert skip.asset == "SalesOrderDetail.SpecialOfferID,ProductID"


# --- Guard 2: end to end, keyless — the derived key repairs the modeler's satellite ----------


def _sales_delta() -> dict[str, Any]:
    return {
        "hubs": [],
        "links": [{"name": "link_sales_order_line",
                   "connected_hubs": ["hub_sales_order", "hub_product"],
                   "description": "A line of a sales order."}],
        "satellites": [{"name": "sat_sales_order_line_detail", "parent": "link_sales_order_line",
                        "attributes": ["OrderQty"], "source_table": "SalesOrderDetail",
                        "description": "Quantity on the line."}],
    }


def _sales_state(schema: list[SourceTable]) -> VaultAgentState:
    state = VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-1", text="Orders have lines.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="product", field="ProductNumber", score=0.95,
                                            rationale="r")],
        existing_model=_vault(),
        source_schemas=schema,
    )
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    return state


async def test_the_derived_key_translates_the_line_satellites_product_participation() -> None:
    state = _sales_state(_sales_schema())
    state = await Dv2ModelerAgent(extractor=StubExtractor(_sales_delta())).run(state)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)

    [link] = [l for l in state.dv_model.links if l.name == "link_sales_order_line"]
    product_ref = next(r for r in link.hub_refs if r.hub == "hub_product")
    assert product_ref.key_translation is not None
    assert product_ref.key_translation.through_table == "Product"
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_sales_order_line_detail"]
    assert sat.participation_translations["hub_product"].through_table == "Product"
    assert not [i for i in state.validation_report.issues if i.code == "E_SAT_KEY_NOT_IN_SOURCE"]


# --- Guards 3 and 4: the remedy, and the memory of it ---------------------------------------


def _routing_schema() -> list[SourceTable]:
    return [
        SourceTable(table="Product", columns=["ProductID", "Name", "ProductNumber"]),
        SourceTable(table="WorkOrder", columns=["WorkOrderID", "ProductID", "OrderQty"]),
        SourceTable(
            table="WorkOrderRouting",
            columns=["WorkOrderID", "ProductID", "OperationSequence", "LocationID",
                     "ActualResourceHrs"],
            foreign_keys=[{"columns": ["WorkOrderID"], "references_table": "WorkOrder",
                           "references_columns": ["WorkOrderID"]}],
        ),
    ]


def _routing_model(sat_parent: str = "link_work_order_operation") -> dict[str, Any]:
    return {
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_work_order", "business_key": "WorkOrderID", "source_entity": "WorkOrder",
             "description": "A work order."},
        ],
        "links": [{"name": "link_work_order_operation",
                   "connected_hubs": ["hub_work_order", "hub_product"],
                   "description": "An operation of a work order on a product."}],
        "satellites": [{"name": "sat_work_order_operation_detail", "parent": sat_parent,
                        "attributes": ["ActualResourceHrs"], "source_table": "WorkOrderRouting",
                        "description": "Hours per operation."}],
    }


def _routing_state() -> VaultAgentState:
    return VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-1", text="Work orders route.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="product", field="ProductNumber", score=0.95,
                                            rationale="r")],
        source_schemas=_routing_schema(),
        modeling_attempts=1,
    )


async def test_the_gate_names_the_parent_whose_key_the_relation_carries_and_retires_the_shape() -> None:
    state = _routing_state()
    state = await Dv2ModelerAgent(extractor=StubExtractor(_routing_model())).run(state)
    state = await ValidatorAgent().run(state)

    [issue] = [i for i in state.validation_report.issues if i.code == "E_SAT_KEY_NOT_IN_SOURCE"]
    assert issue.remedy is not None and "hub_work_order" in issue.remedy
    assert issue.retires == ["sat_work_order_operation_detail"]
    [retired] = state.retired_constructs
    assert (retired.kind, retired.parent, retired.source_table) == (
        "satellite", "link_work_order_operation", "WorkOrderRouting"
    )


async def test_a_satellite_re_emitted_in_the_refused_shape_is_dropped_as_a_decision() -> None:
    state = _routing_state()
    state.retired_constructs = [RetiredConstruct(
        name="sat_work_order_operation_detail", kind="satellite", code="E_SAT_KEY_NOT_IN_SOURCE",
        attempt=1, parent="link_work_order_operation", source_table="WorkOrderRouting",
    )]
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(_routing_model())).run(state)
    finally:
        llm.set_trace_recorder(None)

    assert state.dv_model.satellites == []
    assert [l.name for l in state.dv_model.links] == ["link_work_order_operation"]  # kept
    [flag] = [f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]
    assert flag.asset == "sat_work_order_operation_detail" and "ActualResourceHrs" in flag.message
    assert [e.backstop_id for e in events if e.kind == "backstop"] == ["retired_reemitted"]


async def test_the_same_satellite_re_parented_passes_the_memory() -> None:
    state = _routing_state()
    state.retired_constructs = [RetiredConstruct(
        name="sat_work_order_operation_detail", kind="satellite", code="E_SAT_KEY_NOT_IN_SOURCE",
        attempt=1, parent="link_work_order_operation", source_table="WorkOrderRouting",
    )]
    state = await Dv2ModelerAgent(
        extractor=StubExtractor(_routing_model(sat_parent="hub_work_order"))
    ).run(state)
    assert [s.name for s in state.dv_model.satellites] == ["sat_work_order_operation_detail"]
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]


# --- Guard 5: the demo carries the sales shape ---------------------------------------------


_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "fk_links_postgres" / "build_vault_models.py"
)


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wp46_fk_links_builder", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_the_fk_links_demo_translates_the_line_satellite_through_the_composite_key() -> None:
    builder = _load_builder()
    state = await builder.build_state()
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_sales_order_line_detail"]
    assert sat.participation_translations["hub_product"].through_table == "Product"
    assert not any(i.severity == "error" for i in state.validation_report.issues)
