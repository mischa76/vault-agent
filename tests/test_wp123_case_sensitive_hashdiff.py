"""WP123 (C61) — a hashdiff's input keeps its letter case: each column is derived as the hex of its
trimmed UTF-8 bytes before AutomateDV upper-cases it. Committed before the change, failing (spec
§2)."""

from __future__ import annotations

from typing import Any

import yaml

from vault_agent.agents.staging_generator import build_staging
from vault_agent.rules.platforms import platform_profile
from vault_agent.state import DVModel, SourceColumn, SourceTable


def _table(*columns: tuple[str, str]) -> SourceTable:
    return SourceTable(
        table="contact",
        schema="crm",
        columns=[SourceColumn(name=n, type=t) for n, t in columns],
    )


def _model(*attributes: str) -> DVModel:
    return DVModel.model_validate(
        {
            "hubs": [
                {
                    "name": "hub_contact",
                    "business_key": "ContactID",
                    "source_entity": "contact",
                    "description": "a contact",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_contact_details",
                    "parent": "hub_contact",
                    "attributes": list(attributes),
                    "source_table": "contact",
                    "description": "details",
                }
            ],
        }
    )


def _yaml(sql: str) -> dict[str, Any]:
    block = sql.split("{%- set yaml_metadata -%}")[1].split("{%- endset -%}")[0]
    loaded: dict[str, Any] = yaml.safe_load(block)
    return loaded


def _stage(
    attributes: tuple[str, ...], columns: tuple[tuple[str, str], ...], platform: str = "postgres"
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    result = build_staging(_model(*attributes), [_table(*columns)], target_platform=platform)
    sat = "stg_contact_details"
    return _yaml(result.models[sat]), result.metadata[sat], _yaml(result.models["stg_contact"])


BASE = (("contactid", "integer"), ("segment", "text"), ("modifieddate", "timestamp"))
PG = "ENCODE(CONVERT_TO(NULLIF(TRIM(CAST({} AS text)), ''), 'UTF8'), 'hex')"


def _hashdiff(stage: dict[str, Any]) -> list[str]:
    value = next(v for v in stage["hashed_columns"].values() if isinstance(v, dict))
    columns: list[str] = value["columns"]
    return columns


# ── T1: PostgreSQL — the hashdiff reads derived hex columns, one per attribute ─────────────
def test_the_hashdiff_reads_case_preserving_columns_on_postgres() -> None:
    stage, meta, _ = _stage(("Segment", "ModifiedDate"), BASE)
    assert _hashdiff(stage) == ["MODIFIEDDATE__CS", "SEGMENT__CS"] or sorted(_hashdiff(stage)) == [
        "MODIFIEDDATE__CS",
        "SEGMENT__CS",
    ]
    assert stage["derived_columns"]["SEGMENT__CS"] == PG.format("SEGMENT")
    assert stage["derived_columns"]["MODIFIEDDATE__CS"] == PG.format("MODIFIEDDATE")
    assert meta["derived_columns"]["SEGMENT__CS"] == PG.format("SEGMENT")


# ── T2: Databricks — its own hex function and text type ────────────────────────────────────
def test_databricks_uses_hex_and_string() -> None:
    assert platform_profile("databricks").hex_text == "HEX({})"
    stage, _, _ = _stage(("Segment",), BASE, platform="databricks")
    assert (
        stage["derived_columns"]["SEGMENT__CS"] == "HEX(NULLIF(TRIM(CAST(SEGMENT AS string)), ''))"
    )


# ── T3: hashkeys are untouched — the hub's stage has no derived column ─────────────────────
def test_hashkeys_keep_their_input() -> None:
    stage, _, hub_stage = _stage(("Segment",), BASE)
    assert hub_stage["hashed_columns"] == {"CONTACT_HK": "CONTACTID"}
    assert "derived_columns" not in hub_stage
    assert stage["hashed_columns"]["CONTACT_HK"] == "CONTACTID"


# ── T4: a reserved column is read through its quoted physical name ─────────────────────────
def test_a_reserved_payload_column_is_read_quoted() -> None:
    stage, _, _ = _stage(("Group",), (("contactid", "integer"), ("group", "text")))
    assert stage["derived_columns"]["GROUP__CS"] == PG.format('"group"')


# ── T5: a WP121 cast is read through its derivation ────────────────────────────────────────
def test_an_xml_payload_is_read_through_its_cast() -> None:
    stage, _, _ = _stage(("Resume",), (("contactid", "integer"), ("resume", "xml")))
    assert stage["derived_columns"]["RESUME"] == "CAST(RESUME AS text)"
    assert stage["derived_columns"]["RESUME__CS"] == PG.format("CAST(RESUME AS text)")


# ── T6: the validator's column gate reads what a generator expression reads ────────────────
# WP121's cast and WP123's hex are expressions, not column names; `E_STAGE_COLUMN_NOT_IN_SOURCE`
# must judge the column each one reads (recorded in the stage's metadata), not the
# expression's text.
# WP121 shipped without this: a real run on an `xml` relation would have been refused.
async def test_the_column_gate_accepts_generator_expressions() -> None:
    from vault_agent.agents.code_generator import CodeGeneratorAgent
    from vault_agent.agents.validator import ValidatorAgent
    from vault_agent.state import VaultAgentState

    table = _table(("contactid", "integer"), ("segment", "text"), ("resume", "xml"))
    state = VaultAgentState(
        source_schemas=[table], dv_model=_model("Segment", "Resume"), target_platform="postgres"
    )
    await CodeGeneratorAgent().run(state)
    await ValidatorAgent().run(state)
    codes = [i.code for i in state.validation_report.issues if i.severity == "error"]
    assert "E_STAGE_COLUMN_NOT_IN_SOURCE" not in codes, codes
    meta = state.artifacts.automatedv_yaml["staging"]["stg_contact_details"]
    assert meta["expression_reads"]["RESUME"] == ["RESUME"]
    assert meta["expression_reads"]["RESUME__CS"] == ["RESUME"]
    assert meta["expression_reads"]["SEGMENT__CS"] == ["SEGMENT"]
