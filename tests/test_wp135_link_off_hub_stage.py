"""WP135 (C71) — a link that would share a hub's stage while reading another relation is renamed
after its hubs. Written FIRST. A stage is named after its construct's base, so
`link_product_subcategory` and `hub_product_subcategory` are staged by one model,
`stg_product_subcategory`. The hub reads `ProductSubcategory`; the link's participations are
offered by `Product` alone. One stage cannot read two relations: WP73 refused the hub's binding
for the link's column and both ended on an inferred relation — the demo's second chain
(2026-11-15), and 60 links over the 36 stored chain models. Keyless."""
from __future__ import annotations

from typing import Any

from tests.test_wp41_role_columns_guard import StubExtractor, greenfield_state
from vault_agent import llm
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import DVModel, FlagKind, SourceTable, VaultAgentState

OLD, NEW = "link_product_subcategory", "link_product_product_subcategory"
RENAMED = "link_renamed"  # FlagKind.LINK_RENAMED once it exists
BACKSTOP = "link_off_hub_stage"


def _fk(column: str, table: str, target: str) -> dict[str, Any]:
    return {"columns": [column], "references_table": table, "references_columns": [target],
            "references_schema": "Production"}


def _table(name: str, columns: list[str], pk: list[str], unique: list[list[str]] | None = None,
           fks: list[dict[str, Any]] | None = None) -> SourceTable:
    return SourceTable.model_validate({
        "table": name, "schema": "Production", "columns": columns, "primary_key": pk,
        "unique_keys": unique or [], "foreign_keys": fks or [],
    })


def _schemas() -> list[SourceTable]:
    return [
        _table("Product", ["ProductID", "ProductNumber", "Name", "ProductSubcategoryID"],
               ["ProductID"], [["ProductNumber"]],
               [_fk("ProductSubcategoryID", "ProductSubcategory", "ProductSubcategoryID")]),
        _table("ProductSubcategory", ["ProductSubcategoryID", "Name"],
               ["ProductSubcategoryID"], [["Name"]]),
    ]


def _hub(name: str, key: str, entity: str) -> dict[str, Any]:
    return {"name": name, "business_key": key, "source_entity": entity, "description": "A hub."}


PRODUCT = _hub("hub_product", "ProductNumber", "Product")
SUBCATEGORY = _hub("hub_product_subcategory", "Name", "ProductSubcategory")


def _payload(link: str = OLD, **more: Any) -> dict[str, Any]:
    return {
        "hubs": [PRODUCT, SUBCATEGORY, *more.get("hubs", [])],
        "links": [
            {"name": link, "connected_hubs": ["hub_product", "hub_product_subcategory"],
             "description": "The subcategory a product is placed in."},
            *more.get("links", []),
        ],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "description": "Product attributes."},
            *more.get("satellites", []),
        ],
    }


async def _run(
    payload: dict[str, Any], schemas: list[SourceTable] | None = None,
    state: VaultAgentState | None = None,
) -> tuple[VaultAgentState, list[Any]]:
    state = state or greenfield_state(schemas or _schemas())
    events: list[Any] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    finally:
        llm.set_trace_recorder(None)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    rebind_staging(state)
    return state, [e for e in events if e.kind == "backstop" and e.backstop_id == BACKSTOP]


def _stage(state: VaultAgentState, name: str) -> dict[str, Any]:
    return dict(state.artifacts.automatedv_yaml["staging"][name])


def _relation(meta: dict[str, Any]) -> str:
    source = meta["source_model"]
    return str(next(iter(source.values())) if isinstance(source, dict) else source)


def _links(state: VaultAgentState) -> list[str]:
    return [link.name for link in state.dv_model.links]


# ── the repair ─────────────────────────────────────────────────────────────────────────────────

async def test_a_link_on_a_hubs_stage_reading_another_relation_is_renamed_after_its_hubs() -> None:
    state, _ = await _run(_payload())
    assert _links(state) == [NEW]


async def test_hub_and_link_each_read_their_own_relation() -> None:
    state, _ = await _run(_payload())
    hub = _stage(state, "stg_product_subcategory")
    link = _stage(state, "stg_product_product_subcategory")
    assert (hub["source_binding"], _relation(hub)) == ("declared", "ProductSubcategory")
    assert (link["source_binding"], _relation(link)) == ("declared", "Product")
    [join] = link["key_translation"]["joins"]
    assert (join["through_table"], join["reads"]) == ("ProductSubcategory", "PRODUCTSUBCATEGORYID")
    assert not [f for f in state.flags if f.kind == FlagKind.BINDING_REJECTED]
    assert state.validation_report.passed


async def test_the_links_satellite_follows_it() -> None:
    satellite = {"name": "sat_product_subcategory_assignment", "parent": OLD,
                 "attributes": ["ProductSubcategoryID"], "source_table": "Product",
                 "description": "When the product was placed."}
    state, _ = await _run(_payload(satellites=[satellite]))
    [sat] = [s for s in state.dv_model.satellites if s.name == satellite["name"]]
    assert sat.parent == NEW


async def test_the_rename_is_disclosed_and_counted_as_a_backstop() -> None:
    state, events = await _run(_payload())
    [flag] = [f for f in state.flags if f.kind == RENAMED]
    assert (flag.asset, flag.reason) == (NEW, OLD)
    [event] = events
    assert (event.detail["link"], event.detail["renamed_to"]) == (OLD, NEW)
    assert event.detail["hub"] == "hub_product_subcategory"


async def test_the_next_attempt_is_shown_the_name_the_validator_saw() -> None:
    state, _ = await _run(_payload())
    assert state.previous_delta is not None
    assert [link.name for link in state.previous_delta.links] == [NEW]


async def test_a_role_is_part_of_the_name() -> None:
    schemas = [
        _table("Product", ["ProductID", "ProductNumber"], ["ProductID"], [["ProductNumber"]]),
        _table("UnitMeasure", ["UnitMeasureCode", "Name"], ["UnitMeasureCode"]),
        _table("BillOfMaterials",
               ["BillOfMaterialsID", "ProductAssemblyID", "ComponentID", "UnitMeasureCode"],
               ["BillOfMaterialsID"], None,
               [_fk("ProductAssemblyID", "Product", "ProductID"),
                _fk("ComponentID", "Product", "ProductID"),
                _fk("UnitMeasureCode", "UnitMeasure", "UnitMeasureCode")]),
    ]
    payload = {
        "hubs": [PRODUCT, _hub("hub_unit_measure", "UnitMeasureCode", "UnitMeasure")],
        "links": [{"name": "link_unit_measure", "description": "A component of an assembly.",
                   "connected_hubs": ["hub_product", {"hub": "hub_product", "role": "component"},
                                      "hub_unit_measure"]}],
        "satellites": [{"name": "sat_unit_measure_details", "parent": "hub_unit_measure",
                        "attributes": ["Name"], "description": "The unit's name."}],
    }
    state, _ = await _run(payload, schemas)
    assert _links(state) == ["link_product_product_component_unit_measure"]


# ── what stays ─────────────────────────────────────────────────────────────────────────────────

async def test_a_link_whose_hubs_relation_offers_it_keeps_the_shared_stage() -> None:
    # `ProductReview` carries the review's own key and the product's: hub and link read one
    # relation, one stage serves both (ten such links in the stored chains).
    schemas = [
        _table("Product", ["ProductID", "ProductNumber", "Name"], ["ProductID"]),
        _table("ProductReview", ["ProductReviewID", "ProductID", "Rating"], ["ProductReviewID"],
               None, [_fk("ProductID", "Product", "ProductID")]),
    ]
    payload = {
        "hubs": [_hub("hub_product", "ProductID", "Product"),
                 _hub("hub_product_review", "ProductReviewID", "ProductReview")],
        "links": [{"name": "link_product_review", "description": "A review of a product.",
                   "connected_hubs": ["hub_product_review", "hub_product"]}],
        "satellites": [{"name": "sat_product_review_details", "parent": "hub_product_review",
                        "attributes": ["Rating"], "description": "The rating."}],
    }
    state, events = await _run(payload, schemas)
    assert _links(state) == ["link_product_review"] and not events
    assert _relation(_stage(state, "stg_product_review")) == "ProductReview"


async def test_a_link_no_relation_offers_is_left_alone() -> None:
    # C64's class: nothing says which relation the link reads, so nothing says it is another.
    schemas = [
        _table("Product", ["ProductID", "ProductNumber", "Name"], ["ProductID"],
               [["ProductNumber"]]),
        _table("ProductSubcategory", ["ProductSubcategoryID", "Name"],
               ["ProductSubcategoryID"], [["Name"]]),
    ]
    state, events = await _run(_payload(), schemas)
    assert _links(state) == [OLD] and not events


async def test_a_taken_name_is_not_taken_twice() -> None:
    # The name the rule would give exists: nothing is renamed, the binding is refused and shown
    # as before (WP73) — never a second link of one name.
    other = {"name": NEW, "connected_hubs": ["hub_product", "hub_product_subcategory"],
             "description": "The same relationship under the other name."}
    state, events = await _run(_payload(links=[other]))
    assert sorted(_links(state)) == sorted([OLD, NEW]) and not events
    assert [f.asset for f in state.flags if f.kind == FlagKind.BINDING_REJECTED] == [
        "stg_product_subcategory"
    ]


async def test_a_link_of_the_vault_being_extended_keeps_its_name() -> None:
    existing = DVModel.model_validate(_payload())
    state = greenfield_state(_schemas())
    state.existing_model = existing
    delta = {"hubs": [], "links": [], "satellites": [
        {"name": "sat_product_subcategory_details", "parent": "hub_product_subcategory",
         "attributes": ["Name"], "source_table": "ProductSubcategory",
         "description": "The subcategory's name."}]}
    state, events = await _run(delta, state=state)
    assert _links(state) == [OLD] and not events
