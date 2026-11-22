"""WP100 — two translations in one stage whose natural keys share a name (C33). Committed before the
change, failing. The shape is arm T's fifth project (the C1 experiment, 2026-10-30):
`EmployeeDepartmentHistory` references `Department.DepartmentID` and `Shift.ShiftID`, and both hubs
are keyed on their `Name`. The translation view read `r1.NAME as NAME, r2.NAME as NAME`, dbt refused
the duplicate test, and built, the link would have hashed both hubs from one column."""
from __future__ import annotations

import re

from vault_agent.agents.staging_generator import StagingResult, build_staging
from vault_agent.state import DVModel, SourceTable

DEPARTMENT = SourceTable(table="Department", schema="HumanResources",
                         columns=["DepartmentID", "Name", "GroupName"])
SHIFT = SourceTable(table="Shift", schema="HumanResources",
                    columns=["ShiftID", "Name", "StartTime"])
EMPLOYEE = SourceTable(table="Employee", schema="HumanResources",
                       columns=["BusinessEntityID", "JobTitle"])


def _history(*, with_own_name: bool = False) -> SourceTable:
    columns = ["BusinessEntityID", "DepartmentID", "ShiftID", "StartDate", "ModifiedDate"]
    if with_own_name:
        columns.insert(3, "Name")
    return SourceTable(
        table="EmployeeDepartmentHistory", schema="HumanResources", columns=columns,
        foreign_keys=[
            {"columns": ["DepartmentID"], "references_table": "Department",
             "references_columns": ["DepartmentID"], "references_schema": "HumanResources"},
            {"columns": ["ShiftID"], "references_table": "Shift",
             "references_columns": ["ShiftID"], "references_schema": "HumanResources"},
        ],
    )


def _translation(through: str, surrogate: str) -> dict[str, str]:
    return {"referencing_column": surrogate, "through_table": through,
            "through_schema": "HumanResources", "surrogate_column": surrogate,
            "natural_key_column": "NAME"}


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_employee", "business_key": "BusinessEntityID",
             "source_entity": "Employee", "description": "e"},
            {"name": "hub_department", "business_key": "Name", "source_entity": "Department",
             "description": "d"},
            {"name": "hub_shift", "business_key": "Name", "source_entity": "Shift",
             "description": "s"},
        ],
        "links": [
            {"name": "link_employee_department", "description": "where and when",
             "connected_hubs": [
                 {"hub": "hub_employee"},
                 {"hub": "hub_department",
                  "key_translation": _translation("Department", "DepartmentID")},
                 {"hub": "hub_shift", "key_translation": _translation("Shift", "ShiftID")},
             ]},
        ],
        "satellites": [
            {"name": "sat_employee_department_details", "parent": "link_employee_department",
             "attributes": ["ModifiedDate"], "source_table": "EmployeeDepartmentHistory",
             "description": "when",
             "participation_translations": {
                 "hub_department": _translation("Department", "DepartmentID"),
                 "hub_shift": _translation("Shift", "ShiftID"),
             }},
        ],
    })


def _build(history: SourceTable | None = None) -> StagingResult:
    return build_staging(
        _model(), [EMPLOYEE, DEPARTMENT, SHIFT, history or _history()],
        source_overrides={"EMPLOYEE_DEPARTMENT": "EmployeeDepartmentHistory"},
        target_platform="postgres",
    )


VIEW = "stg_employee_department_via_department_and_shift"


def _aliases(view_sql: str) -> list[str]:
    [projection] = re.findall(r"^select t\.\*, (.*)$", view_sql, flags=re.MULTILINE)
    return [part.split(" as ")[1] for part in projection.split(", ")]


# ── §2 rule 1: the second translation is projected apart ───────────────────────────────────
def test_the_second_translation_projecting_the_same_name_is_pushed_apart() -> None:
    view = _build().models[VIEW]
    assert "r1.NAME as NAME, r2.NAME as NAME_VIA_SHIFT" in view
    assert _aliases(view) == ["NAME", "NAME_VIA_SHIFT"]


# ── §2 rule 2: the hash keys and the link key follow ───────────────────────────────────────
def test_the_stage_hashes_each_hub_from_its_own_column() -> None:
    stage = _build().models["stg_employee_department"]
    assert "DEPARTMENT_HK: 'NAME'" in stage
    assert "SHIFT_HK: 'NAME_VIA_SHIFT'" in stage
    assert ("LINK_EMPLOYEE_DEPARTMENT_HK:\n    - 'BUSINESSENTITYID'\n    - 'NAME'\n"
            "    - 'NAME_VIA_SHIFT'") in stage


def test_the_view_declares_each_projected_column_once() -> None:
    yml = _build().scaffolding[f"models/staging/{VIEW}.yml"]
    assert yml.count("- name: NAME\n") == 1
    assert yml.count("- name: NAME_VIA_SHIFT\n") == 1


def test_the_metadata_records_both_projections() -> None:
    joins = _build().metadata["stg_employee_department"]["key_translation"]["joins"]
    assert [j["projects"] for j in joins] == ["NAME", "NAME_VIA_SHIFT"]


# ── §2 rule 3: the link satellite's dedicated stage follows ────────────────────────────────
def test_the_link_satellites_stage_follows() -> None:
    result = _build()
    view = result.models["stg_employee_department_details_via_department_and_shift"]
    assert _aliases(view) == ["NAME", "NAME_VIA_SHIFT"]
    stage = result.models["stg_employee_department_details"]
    assert "    - 'NAME'\n    - 'NAME_VIA_SHIFT'" in stage


# ── §2 rule 4: WP89 runs after and sees the result ─────────────────────────────────────────
def test_with_the_relations_own_homonym_both_translations_are_pushed_apart() -> None:
    result = _build(_history(with_own_name=True))
    assert _aliases(result.models[VIEW]) == ["NAME_VIA_DEPARTMENT", "NAME_VIA_SHIFT"]
    stage = result.models["stg_employee_department"]
    assert "DEPARTMENT_HK: 'NAME_VIA_DEPARTMENT'" in stage
    assert "SHIFT_HK: 'NAME_VIA_SHIFT'" in stage


# ── §2 rule 5: no rendered translation view projects one alias twice ───────────────────────
def test_no_translation_view_projects_an_alias_twice() -> None:
    for name, sql in _build().models.items():
        if "_via_" in name:
            aliases = _aliases(sql)
            assert len(aliases) == len(set(aliases)), name
