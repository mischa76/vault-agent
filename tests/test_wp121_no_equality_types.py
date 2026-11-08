"""WP121 (C54) — a payload column whose type has no equality is staged as text. Committed before the change,
failing. The shape is the twenty-fifth chain's: `HumanResources.JobCandidate.Resume` is `xml`, and AutomateDV's
satellite merges its ghost record by `UNION`, which PostgreSQL refuses for `xml` (spec §1)."""
from __future__ import annotations

from typing import Any

import pytest
import yaml

from vault_agent.agents.staging_generator import build_staging
from vault_agent.rules.dv2_rules import NO_EQUALITY_TYPES, lacks_equality
from vault_agent.rules.platforms import platform_profile
from vault_agent.state import DVModel, SourceTable


def _cols(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"name": name, "type": type_} for name, type_ in pairs]


def _candidate(resume_type: str) -> SourceTable:
    return SourceTable(table="JobCandidate", schema="HumanResources", columns=_cols(
        ("JobCandidateID", "integer"), ("Resume", resume_type), ("ModifiedDate", "timestamp"),
    ))


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [{"name": "hub_job_candidate", "business_key": "JobCandidateID",
                  "source_entity": "JobCandidate", "description": "a candidate"}],
        "links": [],
        "satellites": [{"name": "sat_job_candidate_details", "parent": "hub_job_candidate",
                        "attributes": ["Resume", "ModifiedDate"], "source_table": "JobCandidate",
                        "description": "the resume"}],
    })


def _stage_yaml(sql: str) -> dict[str, Any]:
    block = sql.split("{%- set yaml_metadata -%}")[1].split("{%- endset -%}")[0]
    loaded: dict[str, Any] = yaml.safe_load(block)
    return loaded


def _stage(resume_type: str, platform: str = "postgres", bound: bool = True) -> tuple[str, dict[str, Any]]:
    tables = [_candidate(resume_type)] if bound else []
    result = build_staging(_model(), tables, target_platform=platform)  # type: ignore[arg-type]
    # the satellite's own stage: it hashes the hashdiff and feeds the satellite (the hub's stage reads the
    # same relation and is cast the same way — every bound stage of it selects the column)
    return result.models["stg_job_candidate_details"], result.metadata["stg_job_candidate_details"]


# ── T1: the rule reads the measured types, nothing else ────────────────────────────────────
@pytest.mark.parametrize("declared", [
    "xml", "XML", " json ", "point", "line", "lseg", "box", "path", "polygon", "circle",
])
def test_types_without_equality(declared: str) -> None:
    assert lacks_equality(declared)


@pytest.mark.parametrize("declared", [
    "jsonb", "text", "varchar(50)", "character varying(4000)", "integer", "uuid", "bytea", "", "AS",
])
def test_types_with_equality_or_unknown(declared: str) -> None:
    assert not lacks_equality(declared)


def test_the_set_is_the_measured_nine() -> None:
    assert NO_EQUALITY_TYPES == frozenset(
        {"xml", "json", "point", "line", "lseg", "box", "path", "polygon", "circle"}
    )


# ── T2: PostgreSQL — the stage derives the column as text, the hashdiff still names it ─────
def test_an_xml_payload_is_derived_as_text_on_postgres() -> None:
    sql, meta = _stage("xml")
    stage = _stage_yaml(sql)
    assert stage["derived_columns"] == {"RESUME": "CAST(RESUME AS text)"}
    assert "derived_columns=metadata_dict['derived_columns']" in sql
    hashdiff = next(v for v in stage["hashed_columns"].values() if isinstance(v, dict))
    assert "RESUME" in hashdiff["columns"]
    assert meta["derived_columns"] == {"RESUME": "CAST(RESUME AS text)"}


# ── T3: Databricks — its unbounded character type, never AutomateDV's VARCHAR(255) ─────────
def test_the_cast_uses_the_platforms_unbounded_text_type() -> None:
    assert platform_profile("postgres").text_type == "text"
    assert platform_profile("databricks").text_type == "string"
    sql, _ = _stage("xml", platform="databricks")
    assert _stage_yaml(sql)["derived_columns"] == {"RESUME": "CAST(RESUME AS string)"}


# ── T4: byte-identity — a relation without such a type renders as before ───────────────────
def test_a_character_payload_gets_no_derived_column() -> None:
    sql, meta = _stage("character varying(4000)")
    assert "derived_columns" not in _stage_yaml(sql)
    assert "derived_columns=none" in sql
    assert "derived_columns" not in meta


# ── T5: an inferred stage has no declared types, so nothing is cast ────────────────────────
def test_an_inferred_stage_is_not_cast() -> None:
    sql, meta = _stage("xml", bound=False)
    assert meta["source_binding"] == "inferred"
    assert "derived_columns" not in _stage_yaml(sql)
