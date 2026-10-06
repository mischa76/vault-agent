"""WP50 — a remedy with memory against the second hub of one person (spec §3). Committed before
the change, failing. The fixture is the fourth chain's step-5 shape (`20261005T234048650821Z`):
`hub_sales_person` on `SalesPerson` keyed `BusinessEntityID` beside `hub_employee`, with
`link_store_sales_person` hashing the sales person from `Store.BusinessEntityID`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import second_hub_remedy
from vault_agent.state import (
    DVModel,
    FlagKind,
    RetiredConstruct,
    SourceTable,
    VaultAgentState,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "wp50" / "step5_store_sales_person.json"
WRONG = "E_LINK_KEY_WRONG_COLUMN"


def _payload() -> dict[str, Any]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return {k: data[k] for k in ("hubs", "links", "satellites")}


def _model() -> DVModel:
    return DVModel.model_validate(_payload())


def _schema(*, onward: bool = True) -> list[SourceTable]:
    """Store, SalesPerson, Employee, BusinessEntity as the sales and HR schemas declare them;
    ``onward=False`` drops SalesPerson's key into Employee, the evidence the remedy needs."""
    sales_person_keys = (
        [{"columns": ["BusinessEntityID"], "references_table": "Employee",
          "references_columns": ["BusinessEntityID"]}] if onward else []
    )
    return [
        SourceTable(table="BusinessEntity", columns=["BusinessEntityID", "rowguid"]),
        SourceTable(table="Employee", columns=["BusinessEntityID", "NationalIDNumber", "JobTitle"]),
        SourceTable(table="SalesPerson", columns=["BusinessEntityID", "TerritoryID", "SalesQuota",
                                                 "Bonus", "CommissionPct", "SalesYTD",
                                                 "SalesLastYear", "ModifiedDate"],
                    foreign_keys=sales_person_keys),
        SourceTable(table="SalesPersonQuotaHistory", columns=["BusinessEntityID", "QuotaDate",
                                                             "SalesQuota"],
                    foreign_keys=[{"columns": ["BusinessEntityID"], "references_table": "SalesPerson",
                                   "references_columns": ["BusinessEntityID"]}]),
        SourceTable(
            table="Store",
            columns=["BusinessEntityID", "Name", "SalesPersonID", "Demographics"],
            foreign_keys=[
                {"columns": ["BusinessEntityID"], "references_table": "BusinessEntity",
                 "references_columns": ["BusinessEntityID"]},
                {"columns": ["SalesPersonID"], "references_table": "SalesPerson",
                 "references_columns": ["BusinessEntityID"]},
            ],
        ),
    ]


def _declared(schema: list[SourceTable]) -> dict[str, SourceTable]:
    from vault_agent.rules.dv2_rules import normalize_identifier
    return {normalize_identifier(t.table): t for t in schema}


# --- Guard 1: the rule ------------------------------------------------------------------------


def test_the_rule_names_the_parent_hub_through_the_onward_key() -> None:
    model = _model()
    sales_person = next(h for h in model.hubs if h.name == "hub_sales_person")
    remedy = second_hub_remedy(sales_person, model, _declared(_schema()))
    assert remedy is not None
    assert remedy.parent == "hub_employee" and remedy.through == "SalesPerson"
    assert "hub_employee" in remedy.text and "do not build" in remedy.text


def test_the_rule_is_silent_without_the_evidence() -> None:
    model = _model()
    sales_person = next(h for h in model.hubs if h.name == "hub_sales_person")
    assert second_hub_remedy(sales_person, model, _declared(_schema(onward=False))) is None
    without_employee = DVModel(hubs=[h for h in model.hubs if h.name != "hub_employee"])
    assert second_hub_remedy(sales_person, without_employee, _declared(_schema())) is None
    store = next(h for h in model.hubs if h.name == "hub_store")
    assert second_hub_remedy(store, model, _declared(_schema())) is None  # BusinessEntity → no hub onward


# --- Guard 2: the gate carries it and retires the hub by shape ------------------------------


async def test_the_wrong_column_gate_carries_the_remedy_and_retires_the_second_hub() -> None:
    state = VaultAgentState(dv_model=_model(), source_schemas=_schema(), modeling_attempts=1)
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == WRONG]
    assert issue.remedy is not None
    assert "hub_employee" in issue.remedy and "SalesPerson" in issue.remedy
    assert issue.retires == ["hub_sales_person"]
    [retired] = [r for r in state.retired_constructs if r.kind == "hub"]
    assert (retired.name, retired.source_entity, retired.key_columns) == (
        "hub_sales_person", "SalesPerson", ["BUSINESSENTITYID"]
    )


async def test_without_the_evidence_the_gate_keeps_todays_message_and_retires_nothing() -> None:
    state = VaultAgentState(dv_model=_model(), source_schemas=_schema(onward=False),
                            modeling_attempts=1)
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == WRONG]
    assert issue.remedy is None and issue.retires == []
    assert not [r for r in state.retired_constructs if r.kind == "hub"]


# --- Guard 3: the memory removes the second hub with its links and satellites ---------------


async def test_the_re_emitted_second_hub_is_dropped_and_the_model_passes_the_gate() -> None:
    state = _state()
    state.source_schemas = _schema()
    state.retired_constructs = [RetiredConstruct(
        name="hub_sales_person", kind="hub", code=WRONG, attempt=1,
        source_entity="SalesPerson", key_columns=["BUSINESSENTITYID"],
    )]
    state = await Dv2ModelerAgent(extractor=StubExtractor(_payload())).run(state)

    names = {h.name for h in state.dv_model.hubs}
    assert "hub_sales_person" not in names and {"hub_store", "hub_employee"} <= names
    link_names = {lk.name for lk in state.dv_model.links}
    assert "link_store_sales_person" not in link_names and "link_store_employee" in link_names
    assert state.dv_model.satellites == []  # the three SalesPerson satellites went with the hub
    orphans = sorted(f.asset for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN)
    assert orphans == ["link_store_sales_person", "sat_sales_person_quota_history",
                       "sat_sales_person_remuneration", "sat_sales_person_running_totals"]
    [sat_flag] = [f for f in state.flags if f.asset == "sat_sales_person_remuneration"]
    assert "SalesQuota" in sat_flag.message

    await ValidatorAgent().run(state)
    assert not [i for i in state.validation_report.issues if i.code == WRONG]
