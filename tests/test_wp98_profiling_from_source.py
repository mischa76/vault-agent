"""WP98 — profiling as a selectable list of deterministic checks, read from the source system
(spec §4, C27 stage 2). Committed red before the change. Keyless: P1 and P2 on SQLite through the
real profiler, P3 on the file, the loader and the two consumers, P4 through Typer's runner."""
from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from typer.testing import CliRunner

from tests.test_wp94_optional_participant import _codes, _state
from vault_agent.agents.source_mapper import SourceMapperAgent
from vault_agent.agents.source_mapper import _Concept as _MapperConcept
from vault_agent.cli import app
from vault_agent.profiler import (
    DEFAULT_CHECKS,
    TableProfile,
    profile_relation,
    profile_tables,
    provenance,
    render_profiling,
    value_shape,
)
from vault_agent.profiling import load_profiling, lookup_profile
from vault_agent.state import ColumnProfile, SourceTable, ValuePattern, VaultAgentState

_DDL = [
    'CREATE TABLE "Customer" ("CustomerID" INTEGER NOT NULL, "AccountNumber" VARCHAR(10), '
    '"Credit" FLOAT, "Since" DATE, "Note" TEXT, "Photo" BLOB)',
    'CREATE TABLE "Empty" ("ID" INTEGER, "Code" VARCHAR(4))',
]
_ROWS = [
    (1, "AW00000001", 10.5, "2020-01-05", "first", b"x"),
    (2, "AW00000002", None, "2021-06-30", None, None),
    (3, "AW00000002", 7.25, None, "third", None),
    (4, None, 10.5, "2019-12-31", "x", None),
    (5, "ZZ-1", 3.0, "2020-01-05", "first", None),
]


@pytest.fixture
def engine(tmp_path: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'main.db'}")
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql(
            'INSERT INTO "Customer" VALUES (?, ?, ?, ?, ?, ?)', _ROWS
        )
    return engine


def _profiles(engine: sa.Engine, **kw: Any) -> dict[str, TableProfile]:
    kw.setdefault("checks", DEFAULT_CHECKS)
    kw.setdefault("sample", 100)
    kw.setdefault("examples", 0)
    return {p.table: p for p in profile_tables(engine, schemas=["main"], tables=None, **kw)}


def _by_name(profile: TableProfile) -> dict[str, ColumnProfile]:
    return {c.name: c for c in profile.columns}


# ── P1 the statistics ───────────────────────────────────────────────────────────────────


def test_p1_counts_are_exact_and_the_ratios_follow_the_definition(engine: sa.Engine) -> None:
    customer = _profiles(engine)["Customer"]
    assert (customer.schema, customer.row_count) == ("main", 5)
    assert [c.name for c in customer.columns] == [
        "CustomerID", "AccountNumber", "Credit", "Since", "Note", "Photo"
    ]
    columns = _by_name(customer)
    assert (columns["CustomerID"].uniqueness_ratio, columns["CustomerID"].null_ratio,
            columns["CustomerID"].distinct_count) == (1.0, 0.0, 5)
    assert (columns["AccountNumber"].uniqueness_ratio, columns["AccountNumber"].null_ratio,
            columns["AccountNumber"].distinct_count) == (0.75, 0.2, 3)
    assert (columns["Photo"].uniqueness_ratio, columns["Photo"].null_ratio,
            columns["Photo"].distinct_count) == (1.0, 0.8, 1)


def test_p1_range_on_numeric_and_temporal_columns_only_lengths_on_character_only(
    engine: sa.Engine,
) -> None:
    columns = _by_name(_profiles(engine)["Customer"])
    assert (columns["CustomerID"].min, columns["CustomerID"].max) == ("1", "5")
    assert (columns["Credit"].min, columns["Credit"].max) == ("3", "10.5")
    assert (columns["Since"].min, columns["Since"].max) == ("2019-12-31", "2021-06-30")
    assert (columns["CustomerID"].min_length, columns["CustomerID"].max_length) == (None, None)
    assert (columns["AccountNumber"].min, columns["AccountNumber"].max) == (None, None), (
        "a character minimum is a row value"
    )
    assert (columns["AccountNumber"].min_length, columns["AccountNumber"].max_length) == (4, 10)
    assert (columns["Note"].min_length, columns["Note"].max_length) == (1, 5)
    photo = columns["Photo"]
    assert (photo.min, photo.max, photo.min_length, photo.max_length, photo.patterns) == (
        None, None, None, None, []
    )


def test_p1_patterns_are_shapes_with_their_share_of_the_sample(engine: sa.Engine) -> None:
    columns = _by_name(_profiles(engine)["Customer"])
    assert columns["AccountNumber"].patterns == [
        ValuePattern(shape="AA99999999", share=0.75), ValuePattern(shape="AA-9", share=0.25)
    ]
    assert columns["Note"].patterns == [
        ValuePattern(shape="AAAAA", share=0.75), ValuePattern(shape="A", share=0.25)
    ]
    assert columns["CustomerID"].patterns == []
    assert value_shape("PO-12345 x") == "AA-99999 A"
    assert value_shape("Müller") == "AAAAAA"
    assert len(value_shape("a" * 40)) == 32


def test_p1_an_empty_table_has_counts_and_nothing_else(engine: sa.Engine) -> None:
    empty = _profiles(engine)["Empty"]
    assert empty.row_count == 0
    for column in empty.columns:
        assert (column.uniqueness_ratio, column.null_ratio, column.distinct_count) == (0.0, 0.0, 0)
        assert (column.min, column.max, column.min_length, column.max_length) == (
            None, None, None, None
        )
        assert column.patterns == [] and column.example_values == []


def test_p1_examples_are_off_by_default_and_selectable(engine: sa.Engine) -> None:
    assert all(
        c.example_values == [] for c in _profiles(engine)["Customer"].columns
    ), "the only check that writes a character column's values is off by default"
    columns = _by_name(
        _profiles(engine, checks=[*DEFAULT_CHECKS, "examples"], examples=2)["Customer"]
    )
    assert columns["AccountNumber"].example_values == ["AW00000001", "AW00000002"]
    assert columns["CustomerID"].example_values == ["1", "2"]
    assert columns["Photo"].example_values == []


def test_p1_check_none_leaves_counts_only(engine: sa.Engine) -> None:
    columns = _by_name(_profiles(engine, checks=[])["Customer"])
    assert columns["CustomerID"].distinct_count == 5
    for column in columns.values():
        assert (column.min, column.max, column.min_length, column.max_length) == (
            None, None, None, None
        )
        assert column.patterns == []


# ── P2 the ladder ───────────────────────────────────────────────────────────────────────


def test_p2_a_column_the_database_refuses_is_omitted_and_named_never_zeroed(
    engine: sa.Engine,
) -> None:
    table = sa.Table("Customer", sa.MetaData(), schema="main", autoload_with=engine)
    warnings: list[str] = []
    with engine.connect() as connection:
        def fetch(statement: sa.Executable) -> Sequence[sa.Row[Any]]:
            if '"Note"' in str(statement.compile(engine)):
                raise sa.exc.OperationalError("refused", {}, Exception("no such operator"))
            return connection.execute(statement).all()

        profile = profile_relation(
            fetch, table, checks=DEFAULT_CHECKS, sample=100, examples=0, warn=warnings.append
        )
    assert [c.name for c in profile.columns] == [
        "CustomerID", "AccountNumber", "Credit", "Since", "Photo"
    ]
    assert profile.row_count == 5 and _by_name(profile)["Credit"].max == "10.5"
    assert len(warnings) == 1 and "Note" in warnings[0]


# ── P3 the file, the loader, the consumers ──────────────────────────────────────────────


def _header() -> str:
    return provenance(
        "postgresql+psycopg2://vault:secret@localhost:5432/vault", ["main"], [],
        checks=DEFAULT_CHECKS, sample=100, examples=0,
    )


def test_p3_the_file_loads_through_the_house_loader_and_is_deterministic(
    engine: sa.Engine, tmp_path: Path
) -> None:
    profiles = profile_tables(
        engine, schemas=["main"], tables=None, checks=DEFAULT_CHECKS, sample=100, examples=0
    )
    text = render_profiling(profiles, header=_header())
    assert text == render_profiling(profiles, header=_header())
    assert "secret" not in text and "vault:***@localhost" in text
    assert "range, lengths, patterns" in text and "sample 100" in text
    path = tmp_path / "profiling.yml"
    path.write_text(text, encoding="utf-8")
    loaded = load_profiling(path)
    assert set(loaded) == {"Customer", "Empty"}
    assert loaded["Customer"] == {c.name: c for c in profiles[0].columns}
    assert loaded["Customer"]["AccountNumber"].patterns[0].shape == "AA99999999"


def test_p3_a_file_without_the_new_keys_loads_with_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "old.yml"
    path.write_text(
        "tables:\n  - table: T\n    columns:\n      - name: C\n        uniqueness_ratio: 0.5\n",
        encoding="utf-8",
    )
    [profile] = load_profiling(path)["T"].values()
    assert (profile.min, profile.max, profile.min_length, profile.max_length) == (
        None, None, None, None
    )
    assert profile.patterns == [] and profile.uniqueness_ratio == 0.5


def _profiled(*, grown: bool) -> dict[str, dict[str, ColumnProfile]]:
    extra: dict[str, Any] = (
        {"min": "1", "max": "9", "min_length": 1, "max_length": 2,
         "patterns": [ValuePattern(shape="9", share=1.0)]} if grown else {}
    )
    return {"Customer": {"CustomerID": ColumnProfile(
        name="CustomerID", uniqueness_ratio=1.0, null_ratio=0.0, distinct_count=9,
        example_values=["1"], **extra,
    )}}


def test_p3_the_mapper_payload_and_the_validator_never_see_the_new_fields() -> None:
    agent = SourceMapperAgent.__new__(SourceMapperAgent)
    concepts = [_MapperConcept("customer", "Customer", "business_key")]
    schemas = [SourceTable(table="Customer", columns=[{"name": "CustomerID", "type": "int"}])]
    grown = json.loads(agent._payload(
        VaultAgentState(source_schemas=schemas, profiling=_profiled(grown=True)), concepts
    ))
    plain = json.loads(agent._payload(
        VaultAgentState(source_schemas=schemas, profiling=_profiled(grown=False)), concepts
    ))
    assert grown == plain and "profiling" in grown["schema"][0]
    assert "max_length" not in json.dumps(grown)


async def test_p3_the_validators_evidence_is_unchanged_by_the_new_fields() -> None:
    plain = _state(nullable=None, profile=0.55)
    grown = _state(nullable=None, profile=0.55)
    profile = grown.profiling["SalesOrderHeader"]["CurrencyRateID"]
    grown.profiling["SalesOrderHeader"]["CurrencyRateID"] = profile.model_copy(update={
        "min": "1", "max": "13532", "patterns": [ValuePattern(shape="9999", share=0.9)],
    })
    assert await _codes(grown) == await _codes(plain)


def test_p3_the_mapper_finds_a_profile_the_way_the_validator_does() -> None:
    profiling = {"salesorderheader": {"salesorderid": ColumnProfile(
        name="salesorderid", uniqueness_ratio=1.0, distinct_count=31465
    )}}
    found = lookup_profile(profiling, "SalesOrderHeader", "SalesOrderID")
    assert found is not None and found.distinct_count == 31465
    assert lookup_profile(profiling, "SalesOrderHeader", "CustomerID") is None
    state = VaultAgentState(profiling=profiling)
    assert "distinct=31465" in SourceMapperAgent._profile_blurb(
        state, "SalesOrderHeader", "SalesOrderID"
    )


# ── P4 the command ──────────────────────────────────────────────────────────────────────


def _url(engine: sa.Engine) -> str:
    return str(engine.url)


def test_p4_without_a_url_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAULT_AGENT_SOURCE_URL", raising=False)
    result = CliRunner().invoke(
        app, ["profile", "--schema", "main", "--out", str(tmp_path / "p.yml")]
    )
    assert result.exit_code == 2 and "VAULT_AGENT_SOURCE_URL" in result.output


def test_p4_without_a_schema_the_command_lists_the_catalogue_and_exits_2(
    engine: sa.Engine, tmp_path: Path
) -> None:
    result = CliRunner().invoke(
        app, ["profile", "--url", _url(engine), "--out", str(tmp_path / "p.yml")]
    )
    assert result.exit_code == 2 and "main" in result.output
    assert not (tmp_path / "p.yml").exists()


def test_p4_an_unknown_check_or_a_table_the_schema_lacks_exits_2(
    engine: sa.Engine, tmp_path: Path
) -> None:
    base = ["profile", "--url", _url(engine), "--schema", "main", "--out", str(tmp_path / "p.yml")]
    result = CliRunner().invoke(app, [*base, "--check", "histogram"])
    assert result.exit_code == 2 and "histogram" in result.output
    result = CliRunner().invoke(app, [*base, "--table", "Nope"])
    assert result.exit_code == 2 and "Nope" in result.output
    assert not (tmp_path / "p.yml").exists()


def test_p4_the_command_writes_the_file_from_the_environment_url(
    engine: sa.Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULT_AGENT_SOURCE_URL", _url(engine))
    out = tmp_path / "p.yml"
    result = CliRunner().invoke(
        app, ["profile", "--schema", "main", "--table", "Customer", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    loaded = load_profiling(out)
    assert list(loaded) == ["Customer"] and loaded["Customer"]["CustomerID"].distinct_count == 5
    assert "2 tables" not in result.output and "1 table" in result.output
