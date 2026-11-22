"""WP75 — a hub with exactly one feed is not multi-source; the WP56 inference never sets a
relation a gate would refuse; one refusal is one review item (spec §3). Committed before the
change, failing. The fixture is the nineteenth chain's step-3 shape: `hub_product` with a single
`HubSource` on `Product`, two history satellites on their own relations."""
from __future__ import annotations

from typing import Any

import pytest

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from vault_agent import llm
from vault_agent.agents import source_mapper
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import (
    hub_is_multi_source,
    single_feed_foreign_relation,
    source_table_on_multi_source_hub,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    PipelineFlag,
    Satellite,
    SourceTable,
    VaultAgentState,
)

PRODUCT = SourceTable(table="Product", columns=["ProductID", "Name", "ProductNumber",
                                                "ListPrice", "ModifiedDate"])
COST = SourceTable(
    table="ProductCostHistory",
    columns=["ProductID", "StartDate", "EndDate", "StandardCost", "ModifiedDate"],
    foreign_keys=[{"columns": ["ProductID"], "references_table": "Product",
                   "references_columns": ["ProductID"]}],
)
PRICE = SourceTable(
    table="ProductListPriceHistory",
    columns=["ProductID", "StartDate", "EndDate", "ListPrice", "ModifiedDate"],
    foreign_keys=[{"columns": ["ProductID"], "references_table": "Product",
                   "references_columns": ["ProductID"]}],
)
VENDOR_PRODUCT = SourceTable(table="VendorProduct", columns=["VendorProductID", "Code"])


def _hub(feeds: int) -> dict[str, Any]:
    sources = [{"source_table": "Product", "business_key_column": "ProductID"},
               {"source_table": "VendorProduct", "business_key_column": "VendorProductID"}]
    return {"name": "hub_product", "business_key": "ProductID", "source_entity": "Product",
            "description": "A product.", "sources": sources[:feeds]}


def _model(feeds: int) -> DVModel:
    return DVModel.model_validate({
        "hubs": [_hub(feeds)],
        "links": [],
        "satellites": [
            {"name": "sat_product_cost_history", "parent": "hub_product",
             "attributes": ["StandardCost", "EndDate"], "source_table": "ProductCostHistory",
             "description": "Cost history."},
            {"name": "sat_product_list_price_history", "parent": "hub_product",
             "attributes": ["ListPrice", "EndDate"], "source_table": "ProductListPriceHistory",
             "description": "Price history."},
        ],
    })


SCHEMA = [PRODUCT, COST, PRICE, VENDOR_PRODUCT]


# ── §3.1 the predicate ─────────────────────────────────────────────────────────────────────
def test_multi_source_means_two_or_more_feeds() -> None:
    one = Hub(**_hub(1))
    two = Hub(**_hub(2))
    none = Hub(**{**_hub(0), "sources": []})
    assert hub_is_multi_source(none) is False
    assert hub_is_multi_source(one) is False
    assert hub_is_multi_source(two) is True
    sat = Satellite(name="s", parent="hub_product", attributes=["StandardCost"],
                    description="d", source_table="ProductCostHistory")
    assert source_table_on_multi_source_hub(sat, one) is False
    assert source_table_on_multi_source_hub(sat, two) is True
    assert single_feed_foreign_relation(sat, one) is True
    assert single_feed_foreign_relation(sat, two) is False
    assert single_feed_foreign_relation(sat.model_copy(update={"source_table": "Product"}),
                                        one) is False  # names the feed: ADR-0011's shape
    assert single_feed_foreign_relation(sat.model_copy(update={"sat_type": "effectivity"}),
                                        one) is False


# ── §3.2 the gate on the nineteenth chain's shape ──────────────────────────────────────────
async def _codes(model: DVModel) -> list[str]:
    state = VaultAgentState(source_schemas=SCHEMA, dv_model=model)
    await ValidatorAgent().run(state)
    return [i.code for i in state.validation_report.issues
            if i.code == "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB"]


async def test_history_satellites_under_a_one_feed_hub_are_not_refused() -> None:
    assert await _codes(_model(1)) == []


async def test_under_two_feeds_the_same_satellites_still_are() -> None:
    assert await _codes(_model(2)) == ["E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB"] * 2


# ── §3.3 the generators ────────────────────────────────────────────────────────────────────
async def test_a_one_feed_hubs_foreign_relation_satellite_is_generated_like_single_source() -> None:
    state = VaultAgentState(source_schemas=SCHEMA, dv_model=_model(1))
    await CodeGeneratorAgent().run(state)
    assert [f for f in state.flags if f.kind == FlagKind.GENERATION_GAP] == []
    sat = state.artifacts.dbt_models["sat_product_cost_history"]
    assert "sat_product_cost_history_product" not in state.artifacts.dbt_models  # not split
    assert "stg_product_cost_history" in sat
    stage = state.artifacts.staging_models["stg_product_cost_history"]
    assert "'ProductCostHistory'" in stage
    assert "PRODUCT_HK" in stage and "PRODUCTID" in stage
    assert "stg_product_product" in state.artifacts.staging_models  # the feed's WP10 stage


# ── §3.4 the inference asks the gate ───────────────────────────────────────────────────────
async def _modeled(payload: dict[str, Any]) -> tuple[VaultAgentState, list[llm.TraceEvent]]:
    state = _state()
    state.source_schemas = SCHEMA
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    finally:
        llm.set_trace_recorder(None)
    return state, events


def _relationless_payload(feeds: int) -> dict[str, Any]:
    return {
        "hubs": [_hub(feeds)],
        "links": [],
        "satellites": [{"name": "sat_product_cost_history", "parent": "hub_product",
                        "attributes": ["StandardCost", "EndDate"],
                        "description": "Cost history."}],
    }


async def test_the_inference_withholds_a_relation_the_multi_source_gate_would_refuse() -> None:
    state, events = await _modeled(_relationless_payload(2))
    [sat] = state.dv_model.satellites
    assert sat.source_table is None
    assert [f for f in state.flags if f.kind == FlagKind.RELATION_INFERRED] == []
    assert not [e for e in events
                if e.kind == "backstop" and e.backstop_id == "satellite_relation_inferred"]


async def test_the_same_satellite_on_a_one_feed_hub_is_inferred_as_before() -> None:
    state, _ = await _modeled(_relationless_payload(1))
    [sat] = state.dv_model.satellites
    assert sat.source_table == "ProductCostHistory"
    assert [f.asset for f in state.flags if f.kind == FlagKind.RELATION_INFERRED] == [
        "sat_product_cost_history"
    ]


# ── §3.5 a re-bind replaces its refusals ───────────────────────────────────────────────────
def test_the_rebind_replaces_earlier_binding_rejected_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The nineteenth chain's step 1: `stg_business_entity_contact` refused once per pass, three
    # identical decisions in the review. The link's stage hashes a role column its relation
    # does not carry, so every pass refuses the override to that relation.
    schema = [
        SourceTable(table="Person", columns=["BusinessEntityID", "FirstName"]),
        SourceTable(table="BusinessEntityContact",
                    columns=["BusinessEntityID", "PersonID", "ContactTypeID"]),
    ]
    model = DVModel.model_validate({
        "hubs": [{"name": "hub_person", "business_key": "BusinessEntityID",
                  "source_entity": "Person", "description": "p"}],
        "links": [{"name": "link_business_entity_contact",
                   "connected_hubs": [{"hub": "hub_person", "role": "contact_person"},
                                      {"hub": "hub_person", "role": "entity"}],
                   "description": "l"}],
        "satellites": [],
    })
    state = VaultAgentState(source_schemas=schema, dv_model=model)
    monkeypatch.setattr(
        source_mapper, "source_overrides",
        lambda _state: {"business_entity_contact": "BusinessEntityContact"},
    )
    source_mapper.rebind_staging(state)
    rejected = [f for f in state.flags if f.kind == FlagKind.BINDING_REJECTED]
    assert len(rejected) == 1, [f.message for f in state.flags]
    # A second pass over a state that already carries the refusal (the code generator's, an
    # earlier attempt's) leaves exactly one.
    state.flags.append(PipelineFlag(**rejected[0].model_dump()))
    source_mapper.rebind_staging(state)
    assert len([f for f in state.flags if f.kind == FlagKind.BINDING_REJECTED]) == 1
