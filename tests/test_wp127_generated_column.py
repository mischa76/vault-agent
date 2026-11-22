"""WP127 (C63, ADR-0021) — the catalogue says whether a column is generated, and the key rule
reads it before the type. Written FIRST. Keyless."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
import yaml
from sqlalchemy.dialects import mssql, postgresql, sqlite

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.source_schema import load_source_schemas
from vault_agent.source_schema_reader import (
    InspectorReader,
    ReadColumn,
    read_source_schema,
    render_source_schema,
)
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    Hub,
    ParsedRequirement,
    Satellite,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)


class _Inspector:
    """What `InspectorReader.columns` reads of SQLAlchemy's Inspector: the dialect and the
    reflected columns (`engine/interfaces.py`, `ReflectedColumn`)."""

    def __init__(self, dialect: Any, columns: list[dict[str, Any]]) -> None:
        self.dialect = dialect
        self._columns = columns

    def get_columns(self, table: str, schema: str | None = None) -> list[dict[str, Any]]:
        return self._columns


def _reflected(name: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "type": sa.Integer(), "nullable": False, "default": None, **extra}


def _generated(dialect: Any, **extra: Any) -> bool | None:
    reader = InspectorReader(_Inspector(dialect, [_reflected("id", **extra)]))  # type: ignore[arg-type]
    return reader.columns("t", "s")[0].generated


# --- the reader ----------------------------------------------------------------------------


def test_an_identity_or_an_autoincrement_column_is_generated_on_any_dialect() -> None:
    for dialect in (postgresql.dialect(), mssql.dialect(), sqlite.dialect()):
        assert _generated(dialect, autoincrement=True) is True
        assert _generated(dialect, autoincrement=False, identity={"start": 1}) is True


def test_not_generated_is_said_only_where_the_dialect_reads_it_from_the_catalogue() -> None:
    assert _generated(postgresql.dialect(), autoincrement=False) is False
    assert _generated(mssql.dialect(), autoincrement=False) is False
    assert _generated(sqlite.dialect(), autoincrement=False) is None  # SQLite sets it for all
    assert _generated(postgresql.dialect()) is None  # the key is absent: the dialect did not say


def test_the_house_file_carries_the_property_only_where_it_is_known(tmp_path: Path) -> None:
    table = SourceTable(table="Customer", schema="dbo", columns=[
        SourceColumn(name="CustomerID", type="int", nullable=False, generated=True),
        SourceColumn(name="CustomerNumber", type="int", nullable=False, generated=False),
        SourceColumn(name="Name", type="nvarchar(50)", nullable=False),
    ], primary_key=["CustomerID"])
    text = render_source_schema([table], header="test")
    columns = yaml.safe_load(text)["source_schemas"][0]["columns"]
    assert [c.get("generated") for c in columns] == [True, False, None]
    assert "generated" not in columns[2]
    path = tmp_path / "schema.yml"
    path.write_text(text, encoding="utf-8")
    [loaded] = load_source_schemas(path)
    assert [c.generated for c in loaded.column_refs] == [True, False, None]


def test_the_reader_passes_the_property_through() -> None:
    class _Reader:
        default_schema = "dbo"

        def table_names(self, schema: str) -> list[str]:
            return ["T"]

        def columns(self, table: str, schema: str) -> list[ReadColumn]:
            return [ReadColumn("ID", "numeric(18, 0)", False, None, generated=True),
                    ReadColumn("Code", "nvarchar(10)", False, None)]

        def primary_key(self, table: str, schema: str) -> list[str]:
            return ["ID"]

        def unique_keys(self, table: str, schema: str) -> list[list[str]]:
            return [["Code"]]

        def foreign_keys(self, table: str, schema: str) -> list[Any]:
            return []

        def table_comment(self, table: str, schema: str) -> str | None:
            return None

    [table] = read_source_schema(_Reader(), schemas=["dbo"], database=None)  # type: ignore[arg-type]
    assert [c.generated for c in table.column_refs] == [True, None]


# --- the rule ------------------------------------------------------------------------------


def _col(name: str, type_: str, generated: bool | None = None) -> SourceColumn:
    return SourceColumn(name=name, type=type_, nullable=False, generated=generated)


def _state(tables: list[SourceTable], keys: list[tuple[str, str, float]]) -> VaultAgentState:
    return VaultAgentState(
        source_schemas=tables,
        business_keys=[BusinessKeyCandidate(entity=e, field=f, score=s, rationale="r")
                       for e, f, s in keys],
        requirements=[ParsedRequirement(id="REQ-001", text="t", category="functional")],
    )


def _decisions(state: VaultAgentState) -> dict[str, Any]:
    from vault_agent.rules.key_decision import decide_keys

    return {d.table: d for d in decide_keys(state)}


def test_a_generated_key_is_technical_whatever_its_type() -> None:
    from vault_agent.rules.key_decision import column_kind

    def partner(type_: str, generated: bool | None) -> SourceTable:
        return SourceTable(table="Partner", columns=[_col("PartnerID", type_, generated),
                                                     _col("PartnerCode", "varchar(12)")],
                           primary_key=["PartnerID"], unique_keys=[["PartnerCode"]])

    # a type that says nothing: generated decides
    table = partner("rowid", True)
    assert column_kind(table, "PartnerID", [table]) == "technical"
    d = _decisions(_state([table], [("partner", "PartnerID", 0.6)]))["Partner"]
    assert (d.basis, d.pending, d.columns) == ("contested", True, ["PartnerCode"])
    silent = partner("rowid", None)
    assert column_kind(silent, "PartnerID", [silent]) == "unknown"
    # Changed while building (spec §5): an exact numeric is technical by its type, like an
    # integer — the `numeric` an Oracle or Db2 identity sits on, where the catalogue is silent.
    numeric = partner("numeric(18, 0)", None)
    assert column_kind(numeric, "PartnerID", [numeric]) == "technical"
    d = _decisions(_state([numeric], [("partner", "PartnerID", 0.6)]))["Partner"]
    assert (d.basis, d.pending, d.columns) == ("contested", True, ["PartnerCode"])


def _customer(generated: bool | None) -> SourceTable:
    return SourceTable(table="Customer", columns=[_col("CustomerNumber", "int", generated),
                                                  _col("Email", "varchar(80)")],
                       primary_key=["CustomerNumber"], unique_keys=[["Email"]])


def test_not_generated_is_no_evidence_that_the_business_assigns_the_key() -> None:
    # Withdrawn while building (spec §5, P3): the spec's rule 4 made an integer key the
    # catalogue calls not generated admissible where the requirements name it first. Read from
    # the local PostgreSQL copy of AdventureWorks, EVERY column is `generated: false` — a copy
    # or a landing zone has no identities — so the rule would have agreed on `AddressTypeID`.
    for generated in (False, None):
        named = _decisions(_state([_customer(generated)], [("customer", "CustomerNumber", 0.9)]))
        assert (named["Customer"].basis, named["Customer"].columns) == ("contested", ["Email"])
        silent = _decisions(_state([_customer(generated)], [("other", "x", 0.9)]))
        assert (silent["Customer"].basis, silent["Customer"].columns) == ("contested", ["Email"])


def test_a_human_keys_the_hub_on_the_business_number_with_a_reason() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision
    from vault_agent.rules.key_decision import check_key_answer

    state = _state([_customer(False)], [("customer", "CustomerNumber", 0.9)])
    refused = check_key_answer(state, "Customer", ["CustomerNumber"], None)
    assert refused is not None and refused.code == "reason_required"
    why = "assigned by the branch, printed on every letter"
    apply_key_decision(
        state, {"keys": {"Customer": {"columns": ["CustomerNumber"], "reason": why}}})
    d = _decisions(state)["Customer"]
    assert (d.columns, d.basis, d.pending) == (["CustomerNumber"], "human", False)


@pytest.mark.asyncio
async def test_that_hub_is_disclosed_with_the_humans_reason() -> None:
    from vault_agent.agents.orchestrator import apply_key_decision

    state = _state([_customer(False)], [("customer", "CustomerNumber", 0.9)])
    apply_key_decision(state, {"keys": {"Customer": {
        "columns": ["CustomerNumber"], "reason": "assigned by the branch"}}})
    state.dv_model = DVModel(
        hubs=[Hub(name="hub_customer", business_key="CustomerNumber", source_entity="Customer",
                  description="c", requirement_ids=["REQ-001"])],
        satellites=[Satellite(name="sat_customer_details", parent="hub_customer",
                              attributes=["Email"], description="d",
                              requirement_ids=["REQ-001"])],
    )
    result = await ValidatorAgent().run(state)
    issues = {i.code: i for i in result.validation_report.issues}
    assert "E_HUB_KEY_NOT_AS_DECIDED" not in issues
    assert "assigned by the branch" in issues["W_HUB_ON_TECHNICAL_KEY"].message
