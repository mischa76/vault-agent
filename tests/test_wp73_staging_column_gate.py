"""WP73 — a staging model is refused when its relation lacks a hashed column; the override loop
stops binding multi-source hubs' links (spec §3). Committed before the change, failing."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.staging_generator import StagingSpec, bind_sources
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import link_source_overrides
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    DVModel,
    FlagKind,
    LinkProposal,
    LinkProposals,
    SourceTable,
    VaultAgentState,
)


def _spec(
    base: str, hashed: list[tuple[str, Any]], derived: dict[str, str] | None = None
) -> StagingSpec:
    spec = StagingSpec(name=f"stg_{base}", base=base)
    for name, value in hashed:
        spec.add_hashed(name, value)
    if derived:
        spec.derived.update(derived)
    return spec


PAY = SourceTable(table="EmployeePayHistory",
                  columns=["BusinessEntityID", "RateChangeDate", "Rate", "ModifiedDate"])
DEPT = SourceTable(table="EmployeeDepartmentHistory",
                   columns=["BusinessEntityID", "DepartmentID", "ShiftID", "StartDate", "EndDate"])


def test_an_override_to_a_relation_lacking_a_hashed_column_is_refused_and_flagged() -> None:
    specs = {"a": _spec("business_entity_department_shift",
                        [("BUSINESSENTITY_HK", "BUSINESSENTITYID"),
                         ("DEPARTMENT_HK", "DEPARTMENTID"),
                         ("LINK_HK", ["BUSINESSENTITYID", "DEPARTMENTID", "SHIFTID"])],
                        {"APPLIED_DTS": "STARTDATE"})}
    key = normalize_identifier("business_entity_department_shift")
    flags = bind_sources(specs, [PAY, DEPT], source_overrides={key: "EmployeePayHistory"})
    spec = specs["a"]
    assert spec.source_model == "raw_business_entity_department_shift" and not spec.bound
    [flag] = [f for f in flags if f.kind == FlagKind.BINDING_REJECTED]
    assert flag.asset == spec.name and flag.reason == "EmployeePayHistory"
    assert "DEPARTMENTID" in flag.message and "SHIFTID" in flag.message
    assert "STARTDATE" in flag.message


def test_an_override_to_a_relation_that_declares_every_column_binds_silently() -> None:
    specs = {"a": _spec("business_entity_department_shift",
                        [("DEPARTMENT_HK", "DEPARTMENTID")], {"APPLIED_DTS": "STARTDATE"})}
    key = normalize_identifier("business_entity_department_shift")
    flags = bind_sources(specs, [PAY, DEPT], source_overrides={key: "EmployeeDepartmentHistory"})
    assert specs["a"].source_model == "EmployeeDepartmentHistory" and specs["a"].bound
    assert flags == []


def test_a_name_match_to_a_relation_lacking_a_hashed_column_is_refused_too() -> None:
    specs = {"a": _spec("employee_pay_history", [("DEPARTMENT_HK", "DEPARTMENTID")])}
    flags = bind_sources(specs, [PAY, DEPT])
    assert specs["a"].source_model == "raw_employee_pay_history"
    assert [f.kind for f in flags] == [FlagKind.BINDING_REJECTED]


def _state_with_license(feeds: list[str]) -> VaultAgentState:
    model = DVModel.model_validate({
        "hubs": [
            {"name": "hub_business_entity", "business_key": "BusinessEntityID",
             "source_entity": "BusinessEntity", "description": "x",
             "sources": [{"source_table": t, "business_key_column": "BusinessEntityID"}
                         for t in feeds]},
            {"name": "hub_department", "business_key": "DepartmentID",
             "source_entity": "Department", "description": "x"},
        ],
        "links": [{"name": "link_business_entity_department",
                   "connected_hubs": ["hub_business_entity", "hub_department"],
                   "description": "x"}],
        "satellites": [],
    })
    schemas = [
        SourceTable(table="BusinessEntity", columns=["BusinessEntityID"]),
        PAY, DEPT,
        SourceTable(table="Department", columns=["DepartmentID", "Name"]),
    ]
    state = VaultAgentState(dv_model=model, source_schemas=schemas)
    # the FK-derived proposal `--accept` ratifies: the pay history's key into the entity hub
    state.link_proposals = LinkProposals(proposals=[LinkProposal(
        source_table="EmployeePayHistory", source_column="BusinessEntityID",
        target_hub="hub_business_entity", target_business_key="BusinessEntityID",
        category="declared_fk_same_name", ratification_status="accepted",
    )])
    return state


def test_the_ratified_loop_leaves_a_multi_source_hubs_link_alone() -> None:
    key = normalize_identifier("business_entity_department")
    multi = link_source_overrides(_state_with_license(["BusinessEntity", "EmployeePayHistory"]))
    assert multi.get(key) != "EmployeePayHistory"
    single = link_source_overrides(_state_with_license(["EmployeePayHistory"]))
    assert single.get(key) == "EmployeePayHistory"


async def test_the_validator_refuses_a_stage_whose_relation_lacks_a_hashed_key() -> None:
    state = VaultAgentState(source_schemas=[PAY, DEPT], dv_model=DVModel.model_validate({
        "hubs": [{"name": "hub_department", "business_key": "DepartmentID",
                  "source_entity": "Department", "description": "x"}],
        "links": [], "satellites": []}))
    state.artifacts.automatedv_yaml = {"staging": {
        "stg_wrong": {"source_model": {"raw": "EmployeePayHistory"},
                      "source_binding": "declared",
                      "hashed_columns": {"DEPARTMENT_HK": "DEPARTMENTID",
                                         "X_HASHDIFF": {"is_hashdiff": True, "columns": ["NOPE"]}},
                      "expected_source_columns": ["DEPARTMENTID"]},
        "stg_right": {"source_model": {"raw": "EmployeeDepartmentHistory"},
                      "source_binding": "declared",
                      "hashed_columns": {"DEPARTMENT_HK": "DEPARTMENTID"},
                      "derived_columns": {"APPLIED_DTS": "STARTDATE"},
                      "expected_source_columns": ["DEPARTMENTID", "STARTDATE"]},
        "stg_inferred": {"source_model": "raw_x", "source_binding": "inferred",
                         "hashed_columns": {"X_HK": "NOPE"}, "expected_source_columns": ["NOPE"]},
        "stg_translated": {"source_model": {"raw": "EmployeePayHistory"},
                           "source_binding": "declared",
                           "hashed_columns": {"X_HK": "NOPE"}, "expected_source_columns": ["NOPE"],
                           "key_translation": {"model": "stg_x", "joins": []}},
    }}
    await ValidatorAgent().run(state)
    hits = [i for i in state.validation_report.issues
            if i.code == "E_STAGE_COLUMN_NOT_IN_SOURCE"]
    assert [i.construct for i in hits] == ["stg_wrong"]
    assert "DEPARTMENTID" in hits[0].message and "EmployeePayHistory" in hits[0].message
