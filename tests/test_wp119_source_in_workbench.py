"""WP119 — the source database in the workbench (C46): the catalogue read and the profile made
through the API, one core with the CLI, byte-identical files, the connection only from the
environment and never a password in an answer. Committed red before the change (spec §4).
Keyless, SQLite as in WP96/WP98."""
from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from vault_agent import profiler
from vault_agent.cli import app as cli_app
from vault_agent.profiler import produce_profiling
from vault_agent.source_schema_reader import (
    SourceDriverMissing,
    UnknownSchemas,
    produce_source_schema,
)
from vault_agent.ui.app import create_app

ENV = "VAULT_AGENT_SOURCE_URL"
_DDL = [
    'CREATE TABLE "Customer" ("CustomerID" INTEGER NOT NULL PRIMARY KEY, '
    '"AccountNumber" VARCHAR(10), "Credit" FLOAT, "Note" TEXT)',
    'CREATE TABLE "Store" ("StoreID" INTEGER NOT NULL PRIMARY KEY, "Name" VARCHAR(40))',
]
_ROWS = [(1, "AW1", 10.5, "a"), (2, "AW2", None, None), (3, "AW2", 7.25, "c")]


@pytest.fixture
def source(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'source.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        connection.exec_driver_sql('INSERT INTO "Customer" VALUES (?, ?, ?, ?)', _ROWS)
        connection.exec_driver_sql("INSERT INTO \"Store\" VALUES (1, 'North')")
    engine.dispose()
    return url


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "projects"))


@pytest.fixture
def project(client: TestClient) -> str:
    return str(client.post("/api/projects", json={"name": "Source demo"}).json()["id"])


def _input(tmp_path: Path, project: str, name: str) -> str:
    return (tmp_path / "projects" / project / "inputs" / name).read_text(encoding="utf-8")


# ── G1 the connection, from the environment only ──────────────────────────────────────────
def test_g1_unset_is_a_state_not_an_error(client: TestClient,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    r = client.get("/api/source")
    assert r.status_code == 200
    assert r.json()["state"] == "unset" and r.json()["url"] is None


def test_g1_a_reachable_source_lists_its_schemas(client: TestClient, source: str,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, source)
    body = client.get("/api/source").json()
    assert body["state"] == "ok" and body["dialect"] == "sqlite" and "main" in body["schemas"]
    tables = client.get("/api/source/tables", params={"schema": "main"}).json()
    assert tables == [{"schema": "main", "table": "Customer"}, {"schema": "main", "table": "Store"}]


def test_g1_a_missing_driver_is_typed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, "postgresql+psycopg2://reader:secret@db.local/aw")

    def missing(url: str) -> Any:
        raise ModuleNotFoundError("No module named 'psycopg2'", name="psycopg2")

    monkeypatch.setattr("vault_agent.source_schema_reader.source_engine", missing)
    body = client.get("/api/source").json()
    assert body["state"] == "driver_missing" and "psycopg2" in body["detail"]
    assert body["url"] == "postgresql+psycopg2://reader:***@db.local/aw"


def test_g1_no_answer_ever_carries_the_password(client: TestClient, project: str,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    # SQLite refuses a URL with credentials, and its message echoes the URL: the unreachable
    # path is the one where a password could leak.
    monkeypatch.setenv(ENV, "sqlite://reader:secret@/nowhere.db")
    answers = [
        client.get("/api/source"),
        client.get("/api/source/tables", params={"schema": "main"}),
        client.post(f"/api/projects/{project}/source-schema", json={"schemas": ["main"]}),
        client.post(f"/api/projects/{project}/profile",
                    json={"schemas": ["main"], "reads_rows": True}),
    ]
    assert answers[0].json()["state"] == "unreachable"
    assert [a.status_code for a in answers[1:]] == [502, 502, 502]
    for answer in answers:
        assert "secret" not in answer.text


# ── G2 the catalogue ──────────────────────────────────────────────────────────────────────
def test_g2_the_catalogue_file_is_the_commands_file(
    client: TestClient, project: str, source: str, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV, source)
    r = client.post(f"/api/projects/{project}/source-schema",
                    json={"schemas": ["main"], "name": "aw.yml"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["file"] == {"kind": "schema", "name": "aw.yml",
                            "bytes": len(_input(tmp_path, project, "aw.yml").encode())}
    assert body["command"] == "vault-agent source-schema --schema main --out inputs/aw.yml"
    out = tmp_path / "cli.yml"
    result = CliRunner().invoke(cli_app, ["source-schema", "--schema", "main", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert _input(tmp_path, project, "aw.yml") == out.read_text(encoding="utf-8")
    listed = client.get(f"/api/projects/{project}").json()["files"]
    assert [f["kind"] for f in listed if f["name"] == "aw.yml"] == ["schema"]


def test_g2_refusals(client: TestClient, project: str, source: str,
                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    r = client.post(f"/api/projects/{project}/source-schema", json={"schemas": ["main"]})
    assert r.status_code == 409 and ENV in r.text
    monkeypatch.setenv(ENV, source)
    r = client.post(f"/api/projects/{project}/source-schema", json={"schemas": ["Sales"]})
    assert r.status_code == 422 and "Sales" in r.text and "main" in r.text
    r = client.post("/api/projects/nope/source-schema", json={"schemas": ["main"]})
    assert r.status_code == 404


# ── G3 the profile ────────────────────────────────────────────────────────────────────────
def test_g3_the_profile_is_the_commands_file(
    client: TestClient, project: str, source: str, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV, source)
    r = client.post(f"/api/projects/{project}/profile", json={
        "schemas": ["main"], "tables": ["Customer"], "checks": ["range", "lengths"],
        "sample": 50, "examples": 2, "name": "prof.yml", "reads_rows": True,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["file"]["kind"] == "profiling" and body["refused"] == []
    command = body["command"]
    assert command == ("vault-agent profile --schema main --table Customer --check range "
                       "--check lengths --check examples --sample 50 --examples 2 "
                       "--out inputs/prof.yml")
    out = tmp_path / "cli.yml"
    result = CliRunner().invoke(cli_app, [
        "profile", "--schema", "main", "--table", "Customer", "--check", "range",
        "--check", "lengths", "--sample", "50", "--examples", "2", "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert _input(tmp_path, project, "prof.yml") == out.read_text(encoding="utf-8")


def test_g3_rows_are_read_only_when_the_request_says_so(
    client: TestClient, project: str, source: str, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV, source)
    for body in ({"schemas": ["main"]}, {"schemas": ["main"], "reads_rows": False}):
        r = client.post(f"/api/projects/{project}/profile", json=body)
        assert r.status_code == 422
    assert not list((tmp_path / "projects" / project / "inputs").iterdir())


def test_g3_refusals_and_a_refused_column(
    client: TestClient, project: str, source: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV, source)
    base = {"schemas": ["main"], "reads_rows": True}
    r = client.post(f"/api/projects/{project}/profile", json={**base, "tables": ["Nope"]})
    assert r.status_code == 422 and "Nope" in r.text and "Customer" in r.text
    r = client.post(f"/api/projects/{project}/profile", json={**base, "checks": ["histogram"]})
    assert r.status_code == 422 and "histogram" in r.text

    real = profiler._fetcher

    def refusing(connection: sa.Connection) -> Any:
        fetch = real(connection)

        def wrapped(statement: sa.Executable) -> Sequence[sa.Row[Any]]:
            if '"Note"' in str(statement.compile(connection.engine)):
                raise sa.exc.OperationalError("refused", {}, Exception("no such operator"))
            return fetch(statement)

        return wrapped

    monkeypatch.setattr(profiler, "_fetcher", refusing)
    r = client.post(f"/api/projects/{project}/profile", json={**base, "tables": ["Customer"]})
    assert r.status_code == 201, r.text
    refused = r.json()["refused"]
    assert len(refused) == 1 and "Note" in refused[0]


# ── G4 one core: the producers raise types, the CLI keeps its codes ───────────────────────
def test_g4_the_producers_raise_types(source: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(UnknownSchemas) as caught:
        produce_source_schema(source, ["Sales"], views=False)
    assert caught.value.missing == ["Sales"] and "main" in caught.value.available
    produced = produce_profiling(source, ["main"], ["Store"], checks=None, sample=10, examples=0)
    assert produced.text.startswith("# read by vault-agent profile from sqlite:///")
    assert produced.checks == ["range", "lengths", "patterns"]

    def missing(url: str) -> Any:
        raise ModuleNotFoundError("No module named 'psycopg2'", name="psycopg2")

    monkeypatch.setattr("vault_agent.source_schema_reader.source_engine", missing)
    with pytest.raises(SourceDriverMissing) as driver:
        produce_source_schema("postgresql+psycopg2://u:p@h/d", ["x"], views=False)
    assert driver.value.module == "psycopg2"


@pytest.fixture(autouse=True)
def _no_leak_between_tests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(ENV, raising=False)
    yield


def test_g4_the_command_record_is_json_safe(client: TestClient, project: str, source: str,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, source)
    r = client.post(f"/api/projects/{project}/source-schema",
                    json={"schemas": ["main"], "views": True})
    assert r.status_code == 201
    assert r.json()["command"].endswith("--views --out inputs/source_schema.yml")
    json.dumps(r.json())
