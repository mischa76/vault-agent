"""WP38 — translated subtype feeds, keyless, on the SalesPerson miniature (spec §5)."""
from __future__ import annotations

import json

from eval.run import model_shape
from tests.test_wp38_subtype_feed_guard import (
    _run,
    existing_vault,
    quota_history,
    sales_person,
    subtype_payload,
    subtype_state,
)
from vault_agent.agents.dv2_modeler import _tool_schema
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import FlagKind, SourceTable
from vault_agent.subtype_feed import ratified_subtype_feeds, subtype_feed


def _proposal():  # type: ignore[no-untyped-def]
    return subtype_state().resolutions.proposals[0]


def test_the_declared_join_makes_the_same_as_a_subtype_feed() -> None:
    feed = subtype_feed(_proposal(), existing_vault(), [sales_person(), quota_history()])
    assert feed is not None
    assert (feed.hub, feed.table) == ("hub_employee", "SalesPerson")
    t = feed.translation
    assert (t.referencing_column, t.through_table, t.surrogate_column, t.natural_key_column) == (
        "BusinessEntityID", "Employee", "BusinessEntityID", "NATIONALIDNUMBER"
    )


def test_two_candidate_subtype_tables_are_not_guessed_between() -> None:
    twin = SourceTable(table="Engineer", columns=["BusinessEntityID", "Level"], foreign_keys=[
        {"columns": ["BusinessEntityID"], "references_table": "Employee",
         "references_columns": ["BusinessEntityID"]}])
    assert subtype_feed(_proposal(), existing_vault(), [sales_person(), twin]) is None


def test_a_table_that_carries_the_hub_key_is_no_translated_feed() -> None:
    carrying = sales_person()
    carrying.columns.append("NationalIDNumber")  # type: ignore[arg-type]
    assert subtype_feed(_proposal(), existing_vault(), [carrying]) is None


def test_an_unratified_same_as_is_not_a_feed_that_acts() -> None:
    state = subtype_state()
    state.resolutions.proposals[0].ratification_status = "proposed"
    assert ratified_subtype_feeds(state.resolutions, existing_vault(), state.source_schemas) == []


async def test_the_applier_translates_the_subtype_satellite_and_flags_it() -> None:
    _, state = await _run(subtype_state(), subtype_payload())
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_sales_person_details"]
    assert sat.key_translation is not None
    [flag] = [f for f in state.flags if f.kind == FlagKind.SAT_TRANSLATION]
    assert flag.asset == "sat_sales_person_details"


async def test_the_modeler_never_sees_the_satellite_translation_field() -> None:
    assert "key_translation" not in json.dumps(_tool_schema())


async def test_the_gates_hold_for_a_ratified_subtype_feed() -> None:
    _, state = await _run(subtype_state(), subtype_payload())
    report = (await ValidatorAgent().run(state)).validation_report
    assert not [i.code for i in report.issues if i.code.startswith("E_SAT_")]


async def test_a_satellite_translation_without_a_ratified_feed_is_refused() -> None:
    _, state = await _run(subtype_state(), subtype_payload())
    state.resolutions.proposals[0].ratification_status = "proposed"
    report = (await ValidatorAgent().run(state)).validation_report
    assert [i.construct for i in report.issues if i.code == "E_SAT_TRANSLATION_UNRATIFIED"] == [
        "sat_sales_person_details"
    ]


async def test_the_surrogate_must_be_declared_on_the_subtype_table() -> None:
    _, state = await _run(subtype_state(), subtype_payload())
    state.source_schemas[0].columns = [c for c in state.source_schemas[0].columns  # type: ignore[assignment]
                                       if getattr(c, "name", c) != "BusinessEntityID"]
    report = (await ValidatorAgent().run(state)).validation_report
    assert "E_SAT_KEY_NOT_IN_SOURCE" in {i.code for i in report.issues}


async def test_the_metadata_and_the_result_file_record_the_join() -> None:
    _, state = await _run(subtype_state(), subtype_payload())
    kt = state.artifacts.automatedv_yaml["staging"]["stg_sales_person_details"]["key_translation"]
    assert kt["joins"][0]["through_table"] == "Employee"
    shape = model_shape(state.dv_model)
    [entry] = [s for s in shape["satellites"] if s["name"] == "sat_sales_person_details"]
    assert entry["translation"]["natural_key_column"] == "NATIONALIDNUMBER"
    untouched = [s for s in shape["satellites"] if s["name"] == "sat_employee_details"]
    assert untouched == [{"name": "sat_employee_details", "parent": "hub_employee"}]
