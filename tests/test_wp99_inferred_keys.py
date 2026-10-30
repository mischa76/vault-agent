"""WP99 — keys inferred from data: unique columns and inclusion dependencies, their own class,
proposed and never accepted by default (spec §4, C27 stage 3, ADR-0018). Committed red before the
change. Keyless: P1 on SQLite through the real inference, P2 on the proposer, the applier and the
prompt, P3 on the file, the inert surfaces and the command."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
import yaml
from rich.console import Console
from typer.testing import CliRunner
from vault_agent.key_inference import compact, infer_keys, is_name_candidate

from tests.test_link_proposal import _vault
from vault_agent import cli
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.cli import app
from vault_agent.existing_model import dump_source_catalogue
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.link_proposal import collect_link_proposals, propose_links
from vault_agent.source_schema import load_source_schemas
from vault_agent.source_schema_reader import render_source_schema
from vault_agent.state import (
    InferredForeignKey,
    InferredKeys,
    InferredUniqueKey,
    SourceTable,
    VaultAgentState,
)

_DDL = [
    'CREATE TABLE "BusinessEntity" ("BusinessEntityID" INTEGER NOT NULL)',
    'CREATE TABLE "Person" ("BusinessEntityID" INTEGER NOT NULL, "Name" VARCHAR(20))',
    'CREATE TABLE "Employee" ("BusinessEntityID" INTEGER NOT NULL, "Title" VARCHAR(20))',
    'CREATE TABLE "SalesPerson" ("BusinessEntityID" INTEGER NOT NULL)',
    'CREATE TABLE "Customer" ("CustomerID" INTEGER NOT NULL, "PersonID" INTEGER)',
    'CREATE TABLE "SalesOrderHeader" ("SalesOrderID" INTEGER NOT NULL, "SalesPersonID" INTEGER, '
    '"CustomerID" INTEGER, "Status" INTEGER)',
]
_ROWS: dict[str, list[tuple[Any, ...]]] = {
    "BusinessEntity": [(i,) for i in range(1, 7)],
    "Person": [(1, "A"), (2, "B"), (3, "A"), (4, "C"), (5, "D")],
    "Employee": [(1, "Eng"), (2, "Eng"), (3, "Ops")],
    "SalesPerson": [(1,), (2,)],
    "Customer": [(1, 2), (2, 3), (3, None)],
    "SalesOrderHeader": [(1, 1, 1, 1), (2, 2, 99, 2), (3, None, 1, 1), (4, None, 99, 2)],
}
_COLUMNS = {
    "BusinessEntity": ["BusinessEntityID"],
    "Person": ["BusinessEntityID", "Name"],
    "Employee": ["BusinessEntityID", "Title"],
    "SalesPerson": ["BusinessEntityID"],
    "Customer": ["CustomerID", "PersonID"],
    "SalesOrderHeader": ["SalesOrderID", "SalesPersonID", "CustomerID", "Status"],
}
_DECLARED = {
    "columns": ["PersonID"], "references_table": "Person",
    "references_columns": ["BusinessEntityID"], "references_schema": "main",
}


@pytest.fixture
def engine(tmp_path: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'main.db'}")
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        for table, rows in _ROWS.items():
            marks = ", ".join("?" for _ in rows[0])
            connection.exec_driver_sql(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    return engine


def _tables() -> list[SourceTable]:
    return [
        SourceTable(
            table=name, schema="main", columns=list(columns),
            foreign_keys=[_DECLARED] if name == "Customer" else [],
        )
        for name, columns in _COLUMNS.items()
    ]


def _by_table(tables: list[SourceTable]) -> dict[str, SourceTable]:
    return {t.table: t for t in tables}


def _fk(table: str, column: str, ref_table: str, *, rows: int, distinct: int,
        referenced: int, wider: list[str], candidate: str = "name") -> InferredForeignKey:
    return InferredForeignKey(
        columns=[column], references_table=ref_table, references_columns=["BusinessEntityID"],
        references_schema="main", rows=rows, distinct=distinct, referenced_distinct=referenced,
        candidate=candidate, wider=wider,
    )


# ── P1 the inference ────────────────────────────────────────────────────────────────────


def test_p1_the_name_tier_infers_exactly_the_inclusions_the_data_holds(engine: sa.Engine) -> None:
    tables = _by_table(infer_keys(engine, _tables(), candidates="name"))
    assert tables["Employee"].inferred_keys is not None
    assert tables["Employee"].inferred_keys.foreign == [_fk(
        "Employee", "BusinessEntityID", "Person", rows=3, distinct=3, referenced=5,
        wider=["BusinessEntity.BusinessEntityID"],
    )]
    assert tables["SalesPerson"].inferred_keys is not None
    assert tables["SalesPerson"].inferred_keys.foreign == [_fk(
        "SalesPerson", "BusinessEntityID", "Employee", rows=2, distinct=2, referenced=3,
        wider=["Person.BusinessEntityID", "BusinessEntity.BusinessEntityID"],
    )]
    assert tables["Person"].inferred_keys is not None
    assert tables["Person"].inferred_keys.foreign == [
        _fk("Person", "BusinessEntityID", "BusinessEntity", rows=5, distinct=5, referenced=6,
            wider=[])
    ]
    header = tables["SalesOrderHeader"].inferred_keys
    assert header is not None
    assert header.foreign == [_fk(
        "SalesOrderHeader", "SalesPersonID", "SalesPerson", rows=2, distinct=2, referenced=2,
        wider=[],
    )], "the table-name rule; CustomerID (99 is absent) and Status (no name path) are not inferred"
    customer = tables["Customer"].inferred_keys
    assert customer is not None and customer.foreign == [], "the declared key is never re-inferred"
    assert tables["BusinessEntity"].inferred_keys is not None
    assert tables["BusinessEntity"].inferred_keys.foreign == []


def test_p1_unique_keys_are_inferred_over_more_than_one_row_and_never_from_a_declaration(
    engine: sa.Engine,
) -> None:
    tables = _by_table(infer_keys(engine, _tables(), candidates="name"))
    def unique(name: str) -> list[InferredUniqueKey]:
        keys = tables[name].inferred_keys
        return keys.unique if keys else []
    assert unique("Person") == [InferredUniqueKey(columns=["BusinessEntityID"], rows=5)]
    assert unique("Employee") == [InferredUniqueKey(columns=["BusinessEntityID"], rows=3)]
    assert unique("Customer") == [InferredUniqueKey(columns=["CustomerID"], rows=3)]
    assert unique("SalesOrderHeader") == [InferredUniqueKey(columns=["SalesOrderID"], rows=4)]
    declared = [t.model_copy(update={"primary_key": ["BusinessEntityID"]}) if t.table == "Person"
                else t for t in _tables()]
    person = _by_table(infer_keys(engine, declared, candidates="name"))["Person"]
    assert person.inferred_keys is not None and person.inferred_keys.unique == []


def test_p1_the_type_tier_is_complete_and_noisy_and_says_which_tier_paired_it(
    engine: sa.Engine,
) -> None:
    header = _by_table(infer_keys(engine, _tables(), candidates="type"))["SalesOrderHeader"]
    assert header.inferred_keys is not None
    status = next(fk for fk in header.inferred_keys.foreign if fk.columns == ["Status"])
    assert (status.references_table, status.candidate) == ("SalesPerson", "type")
    assert status.wider == [
        "Customer.CustomerID", "Employee.BusinessEntityID", "SalesOrderHeader.SalesOrderID",
        "Person.BusinessEntityID", "BusinessEntity.BusinessEntityID",
    ]
    sales_person = next(
        fk for fk in header.inferred_keys.foreign if fk.columns == ["SalesPersonID"]
    )
    assert sales_person.candidate == "name", "a name candidate keeps its tier under the type tier"


def test_p1_the_name_rules() -> None:
    assert compact("Ship_To-Address id") == "SHIPTOADDRESSID"
    assert is_name_candidate("BusinessEntityID", "Person", "BusinessEntityID")
    assert is_name_candidate("ShipToAddressID", "Address", "AddressID")
    assert is_name_candidate("SalesPersonID", "SalesPerson", "BusinessEntityID")
    assert not is_name_candidate("Status", "SalesPerson", "BusinessEntityID")
    assert not is_name_candidate("AddressID", "Address", "ShipToAddressID"), "longer, not shorter"


# ── P2 the proposer, the applier, the prompt ────────────────────────────────────────────


def _employee(*, inferred: bool = True, declared: bool = False) -> SourceTable:
    keys = InferredKeys(foreign=[_fk(
        "Employee", "BusinessEntityID", "Person", rows=3, distinct=3, referenced=5,
        wider=["BusinessEntity.BusinessEntityID"],
    )])
    return SourceTable(
        table="Employee", schema="HumanResources", columns=["BusinessEntityID", "Title"],
        foreign_keys=[{"columns": ["BusinessEntityID"], "references_table": "Person",
                       "references_columns": ["BusinessEntityID"], "references_schema": "Person"}]
        if declared else [],
        inferred_keys=keys if inferred else None,
    )


def _customer_declared() -> SourceTable:
    return SourceTable(table="Customer", schema="Sales", columns=["CustomerID", "PersonID"],
                       foreign_keys=[{**_DECLARED, "references_schema": "Person"}])


def test_p2_an_inferred_key_to_an_existing_hub_is_a_proposal_with_its_provenance() -> None:
    proposals, skipped = propose_links(_vault(), [_employee()])
    assert not skipped and len(proposals.proposals) == 1
    [proposal] = proposals.proposals
    assert (proposal.provenance, proposal.category, proposal.target_hub) == (
        "inferred", "declared_fk_same_name", "hub_person"
    )
    assert "inferred from data, not declared" in proposal.evidence[0]
    assert "3 non-null rows" in proposal.evidence[0] and "5 distinct" in proposal.evidence[0]
    assert "BusinessEntity.BusinessEntityID" in proposal.evidence[0]


def test_p2_a_declared_key_wins_over_the_same_inferred_pair() -> None:
    proposals, _ = propose_links(_vault(), [_employee(inferred=True, declared=True)])
    assert [p.provenance for p in proposals.proposals] == ["declared"]


def test_p2_greenfield_yields_an_inferred_licence() -> None:
    state = VaultAgentState(source_schemas=[
        _employee(), SourceTable(table="Person", schema="Person", columns=["BusinessEntityID"]),
    ])
    state = collect_link_proposals(state)
    assert [lic.provenance for lic in state.link_proposals.licenses] == ["inferred"]


def _pending() -> VaultAgentState:
    state = VaultAgentState(document_path="req.md")
    state.existing_model = _vault()
    state.source_schemas = [_customer_declared(), _employee()]
    return collect_link_proposals(state)


def test_p2_accept_ratifies_the_declared_and_declines_the_inferred() -> None:
    state = _pending()
    assert {p.provenance for p in state.link_proposals.proposals} == {"declared", "inferred"}
    apply_link_decision(state, {"accept": True})
    status = {f"{p.source_table}.{p.source_column}": p.ratification_status
              for p in state.link_proposals.proposals}
    assert status == {"Customer.PersonID": "accepted", "Employee.BusinessEntityID": "overridden"}
    assert state.link_proposals.ratified()[0].provenance == "declared"


def test_p2_an_explicit_link_builds_an_inferred_proposal() -> None:
    state = _pending()
    apply_link_decision(state, {"accept": True, "links": {"Employee.BusinessEntityID": True}})
    assert all(p.ratification_status == "accepted" for p in state.link_proposals.proposals)


class _Prompter:
    def __init__(self, confirms: list[bool]) -> None:
        self._confirms = list(confirms)
        self.asked: list[tuple[str, bool]] = []

    def text(self, console: object, message: str) -> str:
        return ""

    def confirm(self, console: object, message: str, *, default: bool = False) -> bool:
        self.asked.append((message, default))
        return self._confirms.pop(0)


def test_p2_the_prompt_defaults_to_no_for_an_inferred_proposal_and_records_a_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompter = _Prompter([True, True])
    monkeypatch.setattr("vault_agent.cli._prompter", prompter)
    answers = cli._collect_link_decision(Console(), _pending())
    defaults = {message: default for message, default in prompter.asked}
    assert defaults["Build the link for 'Customer.PersonID'?"] is True
    [inferred_question] = [m for m in defaults if "Employee.BusinessEntityID" in m]
    assert defaults[inferred_question] is False and "inferred" in inferred_question
    assert answers == {"Employee.BusinessEntityID": True}, (
        "a yes to an inferred proposal is recorded explicitly, because accept would decline it"
    )


# ── P3 the file, the inert surfaces, the command ────────────────────────────────────────


def test_p3_the_file_carries_the_inferences_and_loads_them_back(tmp_path: Path) -> None:
    tables = [_customer_declared(), _employee()]
    text = render_source_schema(tables, header="h")
    entry = next(e for e in yaml.safe_load(text)["source_schemas"] if e["table"] == "Employee")
    assert list(entry) == ["table", "schema", "columns", "inferred_keys"]
    assert entry["inferred_keys"]["foreign"][0]["candidate"] == "name"
    path = tmp_path / "s.yml"
    path.write_text(text, encoding="utf-8")
    loaded = _by_table(load_source_schemas(path))
    assert loaded["Employee"].inferred_keys == _employee().inferred_keys
    assert loaded["Customer"].inferred_keys is None
    assert "inferred_keys" not in next(
        e for e in yaml.safe_load(text)["source_schemas"] if e["table"] == "Customer"
    )


def test_p3_the_modeler_prompt_and_the_carried_catalogue_never_see_an_inference() -> None:
    with_, without = [_employee()], [_employee(inferred=False)]
    assert render_schema_prompt_section(with_) == render_schema_prompt_section(without)
    assert dump_source_catalogue(with_) == dump_source_catalogue(without)
    assert "inferred" not in render_schema_prompt_section(with_) + dump_source_catalogue(with_)


def test_p3_without_a_url_the_command_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VAULT_AGENT_SOURCE_URL", raising=False)
    schema = tmp_path / "s.yml"
    schema.write_text(render_source_schema(_tables(), header="h"), encoding="utf-8")
    result = CliRunner().invoke(
        app, ["infer-keys", "--source-schema", str(schema), "--out", str(tmp_path / "o.yml")]
    )
    assert result.exit_code == 2 and "VAULT_AGENT_SOURCE_URL" in result.output


def test_p3_the_command_writes_the_file_with_the_inferences(
    engine: sa.Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULT_AGENT_SOURCE_URL", str(engine.url))
    schema, out = tmp_path / "s.yml", tmp_path / "o.yml"
    schema.write_text(render_source_schema(_tables(), header="h"), encoding="utf-8")
    result = CliRunner().invoke(
        app, ["infer-keys", "--source-schema", str(schema), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    loaded = _by_table(load_source_schemas(out))
    assert loaded["Employee"].inferred_keys is not None
    assert loaded["Employee"].inferred_keys.foreign[0].references_table == "Person"
    assert loaded["Customer"].foreign_keys[0].references_table == "Person", "declarations kept"
    assert "4 inferred foreign keys" in result.output
    first = out.read_text(encoding="utf-8")
    CliRunner().invoke(app, ["infer-keys", "--source-schema", str(schema), "--out", str(out)])
    assert out.read_text(encoding="utf-8") == first, "two reads of one database, one file"
