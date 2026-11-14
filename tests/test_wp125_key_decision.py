"""WP125 (C63, ADR-0021) — a hub's key is decided from evidence before the modeler. Written FIRST.

The twenty-third chain's modeler keyed `hub_product` on `ProductID` in its first attempt, against
`REQ-001` and a candidate score of 0.95 for `ProductNumber`; nothing behind it objected. These
guards pin the rule (`rules/key_decision.py`), the given key in the modeler's payload, the gate,
the disclosure and the question at the resolution checkpoint. Keyless.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    ForeignKeyRef,
    Hub,
    HubSource,
    ParsedRequirement,
    Satellite,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "wp125"
DATASETS = ROOT / "eval" / "datasets"
GATE = "E_HUB_KEY_NOT_AS_DECIDED"
DISCLOSURE = "W_HUB_ON_TECHNICAL_KEY"


def _col(name: str, type_: str, nullable: bool | None = False) -> SourceColumn:
    return SourceColumn(name=name, type=type_, nullable=nullable)


def _table(
    name: str, columns: list[SourceColumn], pk: list[str], unique: list[list[str]] | None = None,
    fks: list[ForeignKeyRef] | None = None,
) -> SourceTable:
    return SourceTable(
        table=name, columns=list(columns), primary_key=pk, unique_keys=unique or [],
        foreign_keys=fks or [],
    )


PRODUCT = _table(
    "Product",
    [_col("ProductID", "int"), _col("Name", "nvarchar(50)"), _col("ProductNumber", "nvarchar(25)"),
     _col("rowguid", "uniqueidentifier"), _col("ListPrice", "money")],
    ["ProductID"], [["ProductNumber"], ["Name"], ["rowguid"]],
)
COST_HISTORY = _table(
    "ProductCostHistory",
    [_col("ProductID", "int"), _col("StartDate", "datetime"), _col("StandardCost", "money")],
    ["ProductID", "StartDate"],
    fks=[ForeignKeyRef(columns=["ProductID"], references_table="Product",
                       references_columns=["ProductID"])],
)
ADDRESS_TYPE = _table(
    "AddressType", [_col("AddressTypeID", "int"), _col("Name", "nvarchar(50)")],
    ["AddressTypeID"], [["Name"]],
)
CURRENCY = _table(
    "Currency", [_col("CurrencyCode", "nchar(3)"), _col("Name", "nvarchar(50)")],
    ["CurrencyCode"], [["Name"]],
)
WORK_ORDER = _table(
    "WorkOrder", [_col("WorkOrderID", "int"), _col("OrderQty", "int")], ["WorkOrderID"],
)
PERSON = _table("Person", [_col("BusinessEntityID", "int"), _col("LastName", "nvarchar(50)")],
                ["BusinessEntityID"])
EMPLOYEE = _table(
    "Employee",
    [_col("BusinessEntityID", "int"), _col("NationalIDNumber", "nvarchar(15)"),
     _col("LoginID", "nvarchar(256)"), _col("rowguid", "uniqueidentifier")],
    ["BusinessEntityID"], [["NationalIDNumber"], ["LoginID"], ["rowguid"]],
    fks=[ForeignKeyRef(columns=["BusinessEntityID"], references_table="Person",
                       references_columns=["BusinessEntityID"])],
)


def _bk(entity: str, field: str, score: float) -> BusinessKeyCandidate:
    return BusinessKeyCandidate(entity=entity, field=field, score=score, rationale="r")


def _state(tables: list[SourceTable], keys: list[BusinessKeyCandidate], **kw: Any) -> VaultAgentState:
    return VaultAgentState(
        source_schemas=tables, business_keys=keys,
        requirements=[ParsedRequirement(id="REQ-001", text="t", category="functional")], **kw,
    )


def _decisions(state: VaultAgentState) -> dict[str, Any]:
    from vault_agent.rules.key_decision import decide_keys

    return {d.table: d for d in decide_keys(state)}


# --- the rule ------------------------------------------------------------------------------


def test_the_requirements_first_choice_that_is_a_declared_unique_key_is_the_key() -> None:
    d = _decisions(_state([PRODUCT], [_bk("product", "ProductNumber", 0.95),
                                      _bk("product", "ProductID", 0.15)]))["Product"]
    assert (d.columns, d.basis, d.pending) == (["ProductNumber"], "agreed", False)
    assert d.primary_key_technical is True
    assert d.natural_keys == ["ProductNumber", "Name"]  # the GUID is no identifier


def test_a_technical_primary_key_against_a_declared_natural_key_is_contested() -> None:
    state = _state([ADDRESS_TYPE], [_bk("address type", "AddressTypeID", 0.6),
                                    _bk("address type", "Name", 0.45)])
    d = _decisions(state)["AddressType"]
    assert (d.basis, d.pending) == ("contested", True)
    assert d.columns == ["Name"]  # the default is the declared natural key, never the surrogate


def test_no_candidate_at_all_is_contested_when_the_primary_key_is_technical() -> None:
    d = _decisions(_state([ADDRESS_TYPE], [_bk("other", "Whatever", 0.9)]))["AddressType"]
    assert (d.basis, d.pending, d.columns) == ("contested", True, ["Name"])


def test_a_primary_key_that_is_a_code_stays_without_a_question() -> None:
    d = _decisions(_state([CURRENCY], [_bk("x", "y", 0.5)]))["Currency"]
    assert (d.columns, d.basis, d.pending) == (["CurrencyCode"], "natural_primary_key", False)
    assert d.primary_key_technical is False


def test_a_table_without_a_declared_natural_key_gets_no_decision() -> None:
    assert _decisions(_state([WORK_ORDER, COST_HISTORY], [_bk("work order", "WorkOrderID", 0.7)])) == {}


def test_a_subtypes_primary_key_is_technical_and_the_national_id_is_agreed() -> None:
    d = _decisions(_state([PERSON, EMPLOYEE], [_bk("employee", "NationalIDNumber", 0.85),
                                               _bk("employee", "BusinessEntityID", 0.7)]))
    assert "Person" not in d
    assert (d["Employee"].columns, d["Employee"].basis) == (["NationalIDNumber"], "agreed")
    assert d["Employee"].natural_keys == ["NationalIDNumber", "LoginID"]


def test_a_nullable_unique_column_is_no_natural_key() -> None:
    table = _table("T", [_col("TID", "int"), _col("Code", "nvarchar(10)", nullable=True)],
                   ["TID"], [["Code"]])
    assert _decisions(_state([table], [_bk("t", "Code", 0.9)])) == {}


def test_a_candidate_is_matched_by_a_column_only_its_table_declares() -> None:
    header = _table("SalesOrderHeader", [_col("SalesOrderID", "int"),
                                         _col("SalesOrderNumber", "nvarchar(25)")],
                    ["SalesOrderID"], [["SalesOrderNumber"]])
    d = _decisions(_state([header, PRODUCT], [_bk("sales order", "SalesOrderNumber", 0.9)]))
    assert (d["SalesOrderHeader"].columns, d["SalesOrderHeader"].basis) == (
        ["SalesOrderNumber"], "agreed")


def test_an_untyped_catalogue_decides_nothing() -> None:
    bare = SourceTable(table="Product", columns=["ProductID", "ProductNumber"],
                       primary_key=["ProductID"], unique_keys=[["ProductNumber"]])
    assert _decisions(_state([bare], [_bk("product", "ProductNumber", 0.95)])) == {}


def test_a_table_an_existing_hub_is_built_from_keeps_that_hubs_key() -> None:
    existing = DVModel(hubs=[Hub(name="hub_product", business_key="ProductID",
                                 source_entity="Product", description="p")])
    d = _decisions(_state([PRODUCT], [_bk("product", "ProductNumber", 0.95)],
                          existing_model=existing))["Product"]
    assert (d.basis, d.pending) == ("existing", False)
    assert [c.upper() for c in d.columns] == ["PRODUCTID"]


# --- the answers ---------------------------------------------------------------------------


def _contested() -> VaultAgentState:
    return _state([ADDRESS_TYPE], [_bk("address type", "AddressTypeID", 0.6)])


def test_the_bulk_answer_takes_the_natural_key() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision

    state = _contested()
    assert apply_key_decision(state, {"accept": True}) == ["AddressType"]
    d = _decisions(state)["AddressType"]
    assert (d.columns, d.basis, d.pending) == (["Name"], "catalogue_default", False)


def test_a_resume_that_does_not_name_the_key_still_takes_the_natural_key() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision

    state = _contested()
    apply_key_decision(state, {"links": {"X.Y": True}})
    assert _decisions(state)["AddressType"].basis == "catalogue_default"


def test_the_technical_key_needs_a_reason_and_carries_it() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision
    from vault_agent.rules.key_decision import check_key_answer

    state = _contested()
    error = check_key_answer(state, "AddressType", ["AddressTypeID"], None)
    assert error is not None and error.code == "reason_required"
    assert check_key_answer(state, "AddressType", ["AddressTypeID"], "the name is renamed yearly") is None
    apply_key_decision(state, {"keys": {"AddressType": {
        "columns": ["AddressTypeID"], "reason": "the name is renamed yearly"}}})
    d = _decisions(state)["AddressType"]
    assert (d.columns, d.basis, d.pending, d.reason) == (
        ["AddressTypeID"], "human", False, "the name is renamed yearly")


def test_a_refused_answer_is_not_applied() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision
    from vault_agent.rules.key_decision import check_key_answer

    state = _contested()
    assert check_key_answer(state, "Nowhere", ["Name"], None).code == "unknown_table"  # type: ignore[union-attr]
    assert check_key_answer(state, "AddressType", ["Colour"], None).code == "unknown_column"  # type: ignore[union-attr]
    apply_key_decision(state, {"keys": {"AddressType": {"columns": ["AddressTypeID"]}}})
    assert _decisions(state)["AddressType"].basis == "catalogue_default"  # the default, not the id


def test_naming_the_natural_key_needs_no_reason() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision
    from vault_agent.rules.key_decision import check_key_answer

    state = _contested()
    assert check_key_answer(state, "addresstype", ["name"], None) is None
    apply_key_decision(state, {"keys": {"AddressType": {"columns": ["Name"]}}})
    assert _decisions(state)["AddressType"].basis == "human"


# --- the checkpoint ------------------------------------------------------------------------


def test_a_contested_key_is_pending_at_the_resolution_checkpoint() -> None:
    from vault_agent.rules.key_decision import pending_key_decisions

    state = _contested()
    assert [d.table for d in pending_key_decisions(state)] == ["AddressType"]
    assert pending_key_decisions(_state([PRODUCT], [_bk("product", "ProductNumber", 0.95)])) == []


@pytest.mark.asyncio
async def test_without_a_pending_key_the_checkpoint_does_not_pause() -> None:
    from vault_agent.agents.entity_resolver import ResolutionCheckpointAgent

    state = _state([PRODUCT], [_bk("product", "ProductNumber", 0.95)])
    before = state.model_dump()
    after = await ResolutionCheckpointAgent().run(state)
    assert after.model_dump() == before


# --- the modeler's input -------------------------------------------------------------------


class _Capture:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.seen: dict[str, Any] = {}
        self.system_prompt = ""

    async def model(self, *, system_prompt: str, payload_json: str) -> dict[str, Any]:
        self.seen = json.loads(payload_json)
        self.system_prompt = system_prompt
        return self.payload


_EMPTY_MODEL: dict[str, Any] = {"hubs": [], "links": [], "satellites": []}


@pytest.mark.asyncio
async def test_the_modeler_is_given_the_decided_key() -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent

    capture = _Capture(_EMPTY_MODEL)
    await Dv2ModelerAgent(extractor=capture).run(
        _state([PRODUCT, WORK_ORDER], [_bk("product", "ProductNumber", 0.95)]))
    assert capture.seen["decided_keys"] == [
        {"source_entity": "Product", "business_key": ["ProductNumber"], "basis": "agreed"}]


@pytest.mark.asyncio
async def test_without_a_decision_the_payload_is_todays() -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent

    capture = _Capture(_EMPTY_MODEL)
    await Dv2ModelerAgent(extractor=capture).run(
        _state([WORK_ORDER], [_bk("work order", "WorkOrderID", 0.7)]))
    assert set(capture.seen) == {"requirements", "business_keys"}
    ungrounded = _Capture(_EMPTY_MODEL)
    await Dv2ModelerAgent(extractor=ungrounded).run(_state([], [_bk("customer", "id", 0.7)]))
    assert set(ungrounded.seen) == {"requirements", "business_keys"}


def test_the_two_steering_lines_are_registered_with_a_ledger_row() -> None:
    from vault_agent.rules.dv2_rules import DV_MODELING_RULES

    ids = {rule.id for rule in DV_MODELING_RULES}
    assert {"decided_key_is_given", "reference_attaches_by_translation"} <= ids
    ledger = (ROOT / "docs" / "architecture" / "steering-ledger.md").read_text(encoding="utf-8")
    assert "`decided_key_is_given`" in ledger and "`reference_attaches_by_translation`" in ledger


# --- the gate and the disclosure -----------------------------------------------------------


def _hub(name: str, key: str, entity: str) -> Hub:
    return Hub(name=name, business_key=key, source_entity=entity, description=entity,
               requirement_ids=["REQ-001"])


def _sat(parent: str) -> Satellite:
    return Satellite(name="sat_" + parent[4:] + "_details", parent=parent, attributes=["Name"],
                     description="d", requirement_ids=["REQ-001"])


async def _issues(state: VaultAgentState, code: str) -> list[Any]:
    result = await ValidatorAgent().run(state)
    return [i for i in result.validation_report.issues if i.code == code]


@pytest.mark.asyncio
async def test_a_hub_on_the_surrogate_against_the_decided_key_is_refused_with_a_remedy() -> None:
    state = _state([PRODUCT], [_bk("product", "ProductNumber", 0.95)])
    state.dv_model = DVModel(hubs=[_hub("hub_product", "ProductID", "Product")],
                             satellites=[_sat("hub_product")])
    issues = await _issues(state, GATE)
    assert [(i.severity, i.construct) for i in issues] == [("error", "hub_product")]
    assert issues[0].remedy is not None and "ProductNumber" in issues[0].remedy
    state.dv_model.hubs[0].business_key = "ProductNumber"
    assert await _issues(state, GATE) == []


@pytest.mark.asyncio
async def test_a_multi_source_hub_is_judged_on_its_feed_from_the_decided_table() -> None:
    state = _state([PRODUCT], [_bk("product", "ProductNumber", 0.95)])
    hub = _hub("hub_product", "product number", "Product")
    hub.sources = [HubSource(source_table="Product", business_key_column="ProductID"),
                   HubSource(source_table="LegacyItem", business_key_column="ItemNo")]
    state.dv_model = DVModel(hubs=[hub], satellites=[_sat("hub_product")])
    assert [i.construct for i in await _issues(state, GATE)] == ["hub_product"]


@pytest.mark.asyncio
async def test_a_hub_of_the_existing_vault_is_not_judged() -> None:
    existing = DVModel(hubs=[_hub("hub_product", "ProductID", "Product")],
                       satellites=[_sat("hub_product")])
    state = _state([PRODUCT], [_bk("product", "ProductNumber", 0.95)], existing_model=existing)
    state.dv_model = existing.model_copy(deep=True)
    assert await _issues(state, GATE) == []


@pytest.mark.asyncio
async def test_a_hub_on_a_technical_key_without_a_natural_one_is_disclosed_not_refused() -> None:
    state = _state([WORK_ORDER], [_bk("work order", "WorkOrderID", 0.7)])
    state.dv_model = DVModel(hubs=[_hub("hub_work_order", "WorkOrderID", "WorkOrder")],
                             satellites=[_sat("hub_work_order")])
    assert await _issues(state, GATE) == []
    disclosed = await _issues(state, DISCLOSURE)
    assert [(i.severity, i.construct) for i in disclosed] == [("warning", "hub_work_order")]


@pytest.mark.asyncio
async def test_a_humans_technical_key_is_disclosed_with_the_reason() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision

    state = _contested()
    apply_key_decision(state, {"keys": {"AddressType": {
        "columns": ["AddressTypeID"], "reason": "the name is renamed yearly"}}})
    state.dv_model = DVModel(hubs=[_hub("hub_address_type", "AddressTypeID", "AddressType")],
                             satellites=[_sat("hub_address_type")])
    assert await _issues(state, GATE) == []
    disclosed = await _issues(state, DISCLOSURE)
    assert len(disclosed) == 1 and "the name is renamed yearly" in disclosed[0].message


@pytest.mark.asyncio
async def test_a_code_primary_key_is_neither_refused_nor_disclosed() -> None:
    state = _state([CURRENCY], [_bk("currency", "CurrencyCode", 0.9)])
    state.dv_model = DVModel(hubs=[_hub("hub_currency", "CurrencyCode", "Currency")],
                             satellites=[_sat("hub_currency")])
    assert await _issues(state, GATE) == [] and await _issues(state, DISCLOSURE) == []


# --- P3: the replay of the twenty-third chain's first attempt -------------------------------


@pytest.mark.asyncio
async def test_the_stored_first_attempt_of_the_production_step_is_refused_on_six_hubs() -> None:
    stored = json.loads((FIXTURES / "chain23_step3_attempt1.json").read_text(encoding="utf-8"))
    state = VaultAgentState(
        source_schemas=load_source_schemas(
            DATASETS / "adventureworks_production" / "source_schema.yml"),
        business_keys=[BusinessKeyCandidate.model_validate(c) for c in stored["business_keys"]],
    )
    state.dv_model = DVModel(hubs=[Hub.model_validate(h) for h in stored["hubs"]])
    refused = {i.construct: i for i in await _issues(state, GATE)}
    assert set(refused) == {
        "hub_product", "hub_product_category", "hub_product_subcategory", "hub_product_model",
        "hub_location", "hub_scrap_reason",
    }
    assert "ProductNumber" in (refused["hub_product"].remedy or "")
    assert all("Name" in (refused[h].remedy or "") for h in refused if h != "hub_product")


# --- P4: the count over the five steps ------------------------------------------------------


def test_the_contested_tables_of_the_twenty_third_chain_are_few() -> None:
    from vault_agent.rules.key_decision import decide_keys

    stored = json.loads((FIXTURES / "chain23_business_keys.json").read_text(encoding="utf-8"))
    contested: list[str] = []
    for dataset, candidates in stored.items():
        if dataset.startswith("_"):
            continue
        state = VaultAgentState(
            source_schemas=load_source_schemas(DATASETS / dataset / "source_schema.yml"),
            business_keys=[BusinessKeyCandidate.model_validate(c) for c in candidates],
        )
        contested += [d.table for d in decide_keys(state) if d.pending]
    assert 0 < len(contested) <= 8, contested
    assert "Product" not in contested and "CreditCard" in contested


# --- the CLI's answer ----------------------------------------------------------------------


def test_the_cli_parses_a_key_answer_and_its_reason() -> None:
    from vault_agent.cli import _parse_key_answers

    assert _parse_key_answers(
        ["AddressType=AddressTypeID", "StateProvince=StateProvinceCode+CountryRegionCode"],
        ["AddressType=the name is renamed yearly"],
    ) == {
        "AddressType": {"columns": ["AddressTypeID"], "reason": "the name is renamed yearly"},
        "StateProvince": {"columns": ["StateProvinceCode", "CountryRegionCode"], "reason": None},
    }
