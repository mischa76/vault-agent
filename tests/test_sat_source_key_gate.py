"""E_SAT_KEY_NOT_IN_SOURCE for every satellite with a declared source table — written FIRST,
2026-09-15.

The paid chain `20260914T213855724138Z` passed every gate with `sat_representative_quota_history`
on `hub_employee` read from `SalesPersonQuotaHistory`: its stage hashes `EMPLOYEE_HK` from
`NATIONALIDNUMBER`, which that table does not have, so `dbt build` would fail on it. WP38 had
built the gate for translated satellites only. A satellite's stage computes its parent's hash
key from the parent's key column(s) IN the satellite's own relation (`collect_staging_specs`,
the `source_table` branch); when the relation is declared and lacks them, that is known at model
time and refused there, where the re-model loop can still act.

Grounded runs only; the declared relation must be the one staging binds verbatim; effectivity
satellites, multi-source feeds (ADR-0011, their own gate), translated satellites (WP38's branch)
and pre-existing satellites are out of scope.
"""
from __future__ import annotations

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    LinkHubRef,
    Satellite,
    SourceTable,
    VaultAgentState,
)


def _employee() -> Hub:
    return Hub(name="hub_employee", business_key="NationalIDNumber", source_entity="Employee",
               description="An employee.")


def _territory() -> Hub:
    return Hub(name="hub_sales_territory", business_key="TerritoryID",
               source_entity="SalesTerritory", description="A territory.")


def _quota(source_table: str = "SalesPersonQuotaHistory", **kw: object) -> Satellite:
    return Satellite(name="sat_quota_history", parent="hub_employee", attributes=["SalesQuota"],
                     description="Quota history.", source_table=source_table, **kw)  # type: ignore[arg-type]


SCHEMAS = [
    SourceTable(table="SalesPersonQuotaHistory",
                columns=["BusinessEntityID", "QuotaDate", "SalesQuota"]),
    SourceTable(table="EmployeeQuota", columns=["NationalIDNumber", "SalesQuota"]),
    SourceTable(table="SalesTerritoryHistory",
                columns=["BusinessEntityID", "TerritoryID", "StartDate", "EndDate", "Note"]),
]


async def _codes(model: DVModel, *, schemas: list[SourceTable] = SCHEMAS,
                 existing: DVModel | None = None) -> list[tuple[str, str]]:
    state = VaultAgentState(dv_model=model, source_schemas=schemas, existing_model=existing)
    report = (await ValidatorAgent().run(state)).validation_report
    return [(i.code, i.construct) for i in report.issues if i.code == "E_SAT_KEY_NOT_IN_SOURCE"]


async def test_a_satellite_whose_table_lacks_the_hub_key_is_refused() -> None:
    codes = await _codes(DVModel(hubs=[_employee()], satellites=[_quota()]))
    assert codes == [("E_SAT_KEY_NOT_IN_SOURCE", "sat_quota_history")]


async def test_a_table_that_carries_the_hub_key_passes() -> None:
    assert await _codes(DVModel(hubs=[_employee()], satellites=[_quota("EmployeeQuota")])) == []


async def test_an_undeclared_table_cannot_be_judged_and_passes() -> None:
    assert await _codes(DVModel(hubs=[_employee()], satellites=[_quota("SomewhereElse")])) == []


async def test_a_link_parent_needs_every_participation_key() -> None:
    link = Link(name="link_employee_territory", description="assignment",
                connected_hubs=[LinkHubRef(hub="hub_employee"),
                                LinkHubRef(hub="hub_sales_territory")])
    sat = Satellite(name="sat_assignment_note", parent="link_employee_territory",
                    attributes=["Note"], description="note", source_table="SalesTerritoryHistory")
    codes = await _codes(DVModel(hubs=[_employee(), _territory()], links=[link], satellites=[sat]))
    assert codes == [("E_SAT_KEY_NOT_IN_SOURCE", "sat_assignment_note")]


async def test_effectivity_pre_existing_and_ungrounded_are_out_of_scope() -> None:
    eff = Satellite(name="sat_quota_eff", parent="hub_employee",
                    attributes=["StartDate", "EndDate"], description="eff",
                    source_table="SalesPersonQuotaHistory", sat_type="effectivity")
    assert await _codes(DVModel(hubs=[_employee()], satellites=[eff])) == []
    model = DVModel(hubs=[_employee()], satellites=[_quota()])
    assert await _codes(model, existing=DVModel(hubs=[_employee()], satellites=[_quota()])) == []
    assert await _codes(model, schemas=[]) == []
