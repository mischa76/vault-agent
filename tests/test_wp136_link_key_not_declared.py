"""WP136 (C64) — a link that takes a hub no declared key of its relation leads to. Written FIRST.
`WorkOrderRouting` carries `ProductID` and declares no foreign key to `Product`; the modeler
links an operation to its product all the same (in 36 of the 36 stored chain models). Nothing
then offers the link, its stage reads an inferred relation, and the demo needs a hand view.
Traced at zero cost on the stored runs (2026-11-16), three things were wrong:

* an inferred key a human ACCEPTED (ADR-0018) is resolved, ratified and read by nobody — the
  offer counts declared foreign keys only;
* a hub named after the concept has no stage binding until the mapper's model names a column
  for its key — after the validator, and for a composite key's label not at all — although
  the model itself says which table the hub is built from;
* the review said „no declared source table matched" and nothing about which key is missing.

Keyless."""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import collect_link_proposals
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    FlagKind,
    InferredForeignKey,
    InferredKeys,
    ParsedRequirement,
    Proposal,
    SourceTable,
    VaultAgentState,
)

LINK = "link_work_order_operation"
STAGE = "stg_work_order_operation"
KEY_MISSING = "link_key_missing"  # FlagKind.LINK_KEY_MISSING once it exists


def _fk(column: str, table: str) -> dict[str, Any]:
    return {"columns": [column], "references_table": table, "references_columns": [column],
            "references_schema": "Production"}


def _table(name: str, columns: list[str], pk: list[str], unique: list[list[str]] | None = None,
           fks: list[dict[str, Any]] | None = None,
           inferred: InferredKeys | None = None) -> SourceTable:
    return SourceTable.model_validate({
        "table": name, "schema": "Production", "columns": columns, "primary_key": pk,
        "unique_keys": unique or [], "foreign_keys": fks or [], "inferred_keys": inferred,
    })


def _inferred_product() -> InferredKeys:
    # As `infer-keys` writes it from the data copy: reflected names are lower-case.
    return InferredKeys(foreign=[InferredForeignKey(
        columns=["productid"], references_table="Product", references_columns=["productid"],
        references_schema="Production", rows=67131, distinct=149, referenced_distinct=504,
        candidate="name",
    )])


def _schemas(*, inferred: bool = False, declared: bool = False) -> list[SourceTable]:
    routing_keys = [_fk("LocationID", "Location"), _fk("WorkOrderID", "WorkOrder")]
    if declared:
        routing_keys.append(_fk("ProductID", "Product"))
    return [
        _table("Product", ["ProductID", "ProductNumber", "Name"], ["ProductID"],
               [["ProductNumber"]]),
        _table("Location", ["LocationID", "Name"], ["LocationID"], [["Name"]]),
        _table("WorkOrder", ["WorkOrderID", "ProductID", "OrderQty"], ["WorkOrderID"], None,
               [_fk("ProductID", "Product")]),
        _table("WorkOrderRouting",
               ["WorkOrderID", "ProductID", "OperationSequence", "LocationID", "PlannedCost"],
               ["WorkOrderID", "OperationSequence"], None, routing_keys,
               _inferred_product() if inferred else None),
    ]


def _hub(name: str, key: str, entity: str, **more: Any) -> dict[str, Any]:
    return {"name": name, "business_key": key, "source_entity": entity,
            "description": "A hub.", **more}


OPERATION = _hub("hub_work_order_operation", "work_order_operation", "WorkOrderRouting",
                 business_key_columns=["WorkOrderID", "OperationSequence"])


def _payload(link: str = LINK, hubs: list[str] | None = None) -> dict[str, Any]:
    return {
        "hubs": [
            _hub("hub_product", "ProductNumber", "Product"),
            _hub("hub_location", "Name", "Location"),
            _hub("hub_work_order", "WorkOrderID", "WorkOrder"),
            OPERATION,
        ],
        "links": [
            {"name": link, "description": "An operation, its work order, product and location.",
             "connected_hubs": hubs or ["hub_work_order_operation", "hub_work_order",
                                        "hub_product", "hub_location"]},
            {"name": "link_work_order_product", "description": "The product a work order makes.",
             "connected_hubs": ["hub_work_order", "hub_product"]},
        ],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "description": "The product's name."},
            {"name": "sat_work_order_details", "parent": "hub_work_order",
             "attributes": ["OrderQty"], "description": "The quantity."},
            {"name": "sat_work_order_operation_cost", "parent": "hub_work_order_operation",
             "attributes": ["PlannedCost"], "description": "The planned cost."},
        ],
    }


def _state(schemas: list[SourceTable], *, yes: bool = False) -> VaultAgentState:
    """The resolution checkpoint as the bulk answer leaves it — every declared licence taken,
    every inferred one declined — and, with ``yes``, the one inferred key accepted by name."""
    state = VaultAgentState(
        requirements=[ParsedRequirement(id="REQ-1", text="Operations are costed.",
                                        category="functional")],
        business_keys=[BusinessKeyCandidate(entity="product", field="ProductNumber", score=0.9,
                                            rationale="r")],
        source_schemas=schemas,
    )
    collect_link_proposals(state)
    decision: dict[str, Any] = {"accept": True}
    if yes:
        decision["links"] = {"WorkOrderRouting.productid": True}
    apply_link_decision(state, decision)
    return state


async def _run(state: VaultAgentState, payload: dict[str, Any] | None = None) -> VaultAgentState:
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload or _payload())).run(state)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    assert state.validation_report.passed, [
        (i.code, i.construct, i.message) for i in state.validation_report.issues
        if i.severity == "error"
    ]
    rebind_staging(state)
    return state


def _stage(state: VaultAgentState, name: str = STAGE) -> dict[str, Any]:
    return dict(state.artifacts.automatedv_yaml["staging"][name])


def _relation(meta: dict[str, Any]) -> str:
    source = meta["source_model"]
    return str(next(iter(source.values())) if isinstance(source, dict) else source)


def _joins(meta: dict[str, Any]) -> dict[str, str]:
    joins = (meta.get("key_translation") or {}).get("joins") or []
    return {join["through_table"]: join["reads"] for join in joins}


def _flags(state: VaultAgentState, kind: str) -> list[Any]:
    return [f for f in state.flags if f.kind == kind]


# ── an inferred key a human accepted is a key of its relation ──────────────────────────────────

async def test_an_accepted_inferred_key_binds_the_link_and_translates_its_participation() -> None:
    state = await _run(_state(_schemas(inferred=True), yes=True))
    stage = _stage(state)
    assert (stage["source_binding"], _relation(stage)) == ("declared", "WorkOrderRouting")
    assert _joins(stage) == {"Product": "PRODUCTID", "Location": "LOCATIONID"}
    assert not _flags(state, FlagKind.BINDING_REJECTED)
    assert not _flags(state, FlagKind.SOURCE_BINDING)
    assert not _flags(state, KEY_MISSING)


async def test_the_accepted_key_reads_like_the_declared_one() -> None:
    # What a declaration in the catalogue did all along is the measure: same binding, same joins.
    declared = _stage(await _run(_state(_schemas(declared=True))))
    accepted = _stage(await _run(_state(_schemas(inferred=True), yes=True)))
    assert _relation(accepted) == _relation(declared) == "WorkOrderRouting"
    assert _joins(accepted) == _joins(declared)
    assert accepted["hashed_columns"] == declared["hashed_columns"]


async def test_the_translation_under_an_inferred_key_is_a_decision_to_confirm() -> None:
    # WP128: inferred from data, not declared — the human who said yes at the checkpoint is
    # shown what was built on it.
    state = await _run(_state(_schemas(inferred=True), yes=True))
    [flag] = [f for f in _flags(state, FlagKind.LINK_TRANSLATION)
              if (f.asset or "").upper() == "WORKORDERROUTING.PRODUCTID"]
    assert flag.confirm


async def test_an_inferred_key_nobody_accepted_changes_nothing() -> None:
    # ADR-0018 §4: never accepted by default — the bulk answer declines it, and the binder
    # reads only what a human took.
    state = await _run(_state(_schemas(inferred=True)))
    assert _stage(state)["source_binding"] == "inferred"
    assert "Product" not in _joins(_stage(state))


async def test_a_link_with_a_stage_of_its_own_binds_by_the_accepted_key() -> None:
    # The first chain of 2026-11-15 named it apart from the hub: no shared stage, the offer alone.
    state = await _run(
        _state(_schemas(inferred=True), yes=True), _payload("link_work_order_operation_location")
    )
    stage = _stage(state, "stg_work_order_operation_location")
    assert (stage["source_binding"], _relation(stage)) == ("declared", "WorkOrderRouting")
    assert _joins(stage) == {"Product": "PRODUCTID", "Location": "LOCATIONID"}


# ── a new hub is bound to the table its own model names, before the validator ─────────────────

HUB_ONLY = ["hub_work_order_operation", "hub_work_order"]


async def _generate(state: VaultAgentState, payload: dict[str, Any]) -> VaultAgentState:
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    return await CodeGeneratorAgent().run(state)


async def test_a_hub_named_after_the_concept_is_bound_by_its_provenance() -> None:
    # No mapper has run: the model's own word (`source_entity`) binds the stage at generation.
    state = await _generate(_state(_schemas()), _payload("link_operation_work_order", HUB_ONLY))
    stage = _stage(state)
    assert (stage["source_binding"], _relation(stage)) == ("declared", "WorkOrderRouting")
    assert not [f for f in _flags(state, FlagKind.SOURCE_BINDING) if f.asset == STAGE]


async def test_the_gates_judge_the_stage_they_could_not_see() -> None:
    # The relation is unique on three columns, the hub is keyed on two: bound before the
    # validator, the satellite on it is refused there (WP85) — as WP134 refuses the same
    # binding from a human at sign-off — instead of being bound behind the gate.
    schemas = _schemas()
    schemas[3] = _table(
        "WorkOrderRouting",
        ["WorkOrderID", "ProductID", "OperationSequence", "LocationID", "PlannedCost"],
        ["WorkOrderID", "ProductID", "OperationSequence"], None,
        [_fk("LocationID", "Location"), _fk("WorkOrderID", "WorkOrder")],
    )
    state = await _generate(_state(schemas), _payload("link_operation_work_order", HUB_ONLY))
    state = await ValidatorAgent().run(state)
    refused = [i.construct for i in state.validation_report.issues
               if i.code == "E_SAT_GRAIN_NOT_UNIQUE"]
    assert refused == ["sat_work_order_operation_cost"]


async def test_the_mappers_answer_still_comes_first() -> None:
    archive = _table("WorkOrderRoutingArchive",
                     ["WorkOrderID", "OperationSequence", "ArchivedCost"],
                     ["WorkOrderID", "OperationSequence"])
    payload = _payload("link_operation_work_order", HUB_ONLY)
    payload["satellites"].append({
        "name": "sat_work_order_operation_archive", "parent": "hub_work_order_operation",
        "attributes": ["ArchivedCost"], "source_table": "WorkOrderRoutingArchive",
        "description": "The archived cost."})
    state = await _generate(_state([*_schemas(), archive]), payload)
    state.mappings.proposals.append(Proposal(
        concept="work_order_operation", entity="WorkOrderRouting",
        table="WorkOrderRoutingArchive", column="OperationSequence", confidence=0.9,
    ))
    rebind_staging(state)
    assert _relation(_stage(state)) == "WorkOrderRoutingArchive"


def _provenance(model: DVModel, existing: DVModel | None) -> dict[str, str]:
    from vault_agent.agents.staging_generator import hub_provenance  # exists once WP136 is built

    return dict(hub_provenance(model, _schemas(), existing))


def test_a_hub_of_the_vault_being_extended_keeps_the_binding_it_carries() -> None:
    model = DVModel.model_validate(_payload())
    assert _provenance(model, None) == {"WORK_ORDER_OPERATION": "WorkOrderRouting"}
    assert _provenance(model, model) == {}


def test_a_hub_named_like_its_table_is_left_to_the_name_rule() -> None:
    named = _provenance(DVModel.model_validate(_payload()), None)
    assert "WORK_ORDER" not in named and "PRODUCT" not in named and "LOCATION" not in named


# ── which key is missing, said where the stage stays inferred ──────────────────────────────────

async def test_an_unoffered_link_is_told_which_key_its_relation_lacks() -> None:
    state = await _run(_state(_schemas()))
    assert _stage(state)["source_binding"] == "inferred"
    [flag] = _flags(state, KEY_MISSING)
    assert (flag.asset, flag.reason) == (LINK, "WorkOrderRouting")
    assert "hub_product" in flag.message and "WorkOrderRouting.ProductID" in flag.message
    assert "Product.ProductID" in flag.message and "infer-keys" in flag.message


async def test_the_name_is_a_pointer_and_binds_nothing() -> None:
    # WP34's rejected name-only tier stays rejected: the column is named, never joined on.
    state = await _run(_state(_schemas()))
    assert "Product" not in _joins(_stage(state))
    link = next(link for link in state.dv_model.links if link.name == LINK)
    assert all(ref.key_translation is None or ref.hub != "hub_product" for ref in link.hub_refs)


async def test_a_link_its_relation_offers_is_told_nothing() -> None:
    state = await _run(_state(_schemas(declared=True)))
    assert not _flags(state, KEY_MISSING)


async def test_a_column_named_like_a_natural_key_is_no_pointer() -> None:
    # `Location.Name` is a declared unique key and `Product.Name` is the product's name: a
    # natural key's name recurs as an attribute. Only a primary key's name is pointed at.
    schemas = [
        _table("Product", ["ProductID", "ProductNumber", "Name"], ["ProductID"],
               [["ProductNumber"]]),
        _table("Location", ["Code", "Name"], ["Code"], [["Name"]]),
    ]
    payload = {
        "hubs": [_hub("hub_product", "ProductNumber", "Product"),
                 _hub("hub_location", "Name", "Location")],
        "links": [{"name": "link_product_location", "description": "Where a product is.",
                   "connected_hubs": ["hub_product", "hub_location"]}],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "description": "The product's name."},
            {"name": "sat_location_details", "parent": "hub_location", "attributes": ["Code"],
             "description": "The location's code."},
        ],
    }
    state = await _run(_state(schemas), payload)
    assert _stage(state, "stg_product_location")["source_binding"] == "inferred"
    assert not _flags(state, KEY_MISSING)
