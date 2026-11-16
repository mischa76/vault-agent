"""WP140 — keys inferred from the workbench (C74, spec §4): `vault-agent infer-keys` through the
API, one core with the command, the byte-identical file, the row read acknowledged in the
request, and the checkpoint's pending list carrying a proposal's provenance as a typed field.
Committed red before the change. Keyless, SQLite as in WP99/WP119."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from vault_agent.cli import app as cli_app
from vault_agent.state import (
    KeyLicense,
    LinkProposal,
    LinkProposals,
    Participation,
    RelationshipLinkProposal,
    VaultAgentState,
)
from vault_agent.ui.app import create_app
from vault_agent.ui.runs import _pending_links

ENV = "VAULT_AGENT_SOURCE_URL"
_DDL = [
    'CREATE TABLE "Product" ("ProductID" INTEGER NOT NULL PRIMARY KEY, "Name" VARCHAR(20))',
    'CREATE TABLE "Routing" ("RoutingID" INTEGER NOT NULL PRIMARY KEY, '
    '"ProductID" INTEGER NOT NULL, "Note" TEXT)',
]
_ROWS: dict[str, list[tuple[Any, ...]]] = {
    "Product": [(1, "a"), (2, "b"), (3, "c")],
    "Routing": [(1, 2, "x"), (2, 3, "x"), (3, 2, "y")],
}


class UndefinedFunctionError(Exception):
    """Stands for the driver's error: no equality operator for the column's type."""


@pytest.fixture
def source(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'source.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        for statement in _DDL:
            connection.exec_driver_sql(statement)
        for table, rows in _ROWS.items():
            marks = ", ".join("?" for _ in rows[0])
            connection.exec_driver_sql(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    engine.dispose()
    return url


@pytest.fixture(autouse=True)
def _no_leak_between_tests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(ENV, raising=False)
    yield


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "projects"))


@pytest.fixture
def project(client: TestClient) -> str:
    return str(client.post("/api/projects", json={"name": "Keys demo"}).json()["id"])


@pytest.fixture
def catalogue(client: TestClient, project: str, source: str,
              monkeypatch: pytest.MonkeyPatch) -> str:
    """The project with the catalogue read through the workbench — no foreign key declared."""
    monkeypatch.setenv(ENV, source)
    r = client.post(f"/api/projects/{project}/source-schema",
                    json={"schemas": ["main"], "name": "aw.yml"})
    assert r.status_code == 201, r.text
    assert r.json()["summary"]["foreign_keys"] == 0
    return project


def _inputs(tmp_path: Path, project: str) -> Path:
    return tmp_path / "projects" / project / "inputs"


# ── G1 the route writes the command's file ────────────────────────────────────────────────
def test_g1_the_inferred_file_is_the_commands_file(
    client: TestClient, catalogue: str, tmp_path: Path,
) -> None:
    r = client.post(f"/api/projects/{catalogue}/infer-keys",
                    json={"schema": "aw.yml", "name": "aw_keys.yml", "reads_rows": True})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["command"] == ("vault-agent infer-keys --source-schema inputs/aw.yml "
                               "--candidates name --out inputs/aw_keys.yml")
    written = (_inputs(tmp_path, catalogue) / "aw_keys.yml").read_text(encoding="utf-8")
    assert body["file"] == {"kind": "schema", "name": "aw_keys.yml", "command": body["command"],
                            "bytes": len(written.encode())}
    assert body["summary"] == {"tables": 2, "tables_read": 2, "unique": 1, "foreign": 1}
    assert body["refused"] == []
    out = tmp_path / "cli.yml"
    result = CliRunner().invoke(cli_app, [
        "infer-keys", "--source-schema", str(_inputs(tmp_path, catalogue) / "aw.yml"),
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert written == out.read_text(encoding="utf-8")
    assert "references_table: Product" in written and "inferred_keys" in written
    listed = client.get(f"/api/projects/{catalogue}").json()["files"]
    assert sorted(f["name"] for f in listed if f["kind"] == "schema") == ["aw.yml", "aw_keys.yml"]


def test_g1_without_a_name_the_input_is_replaced(
    client: TestClient, catalogue: str, tmp_path: Path,
) -> None:
    r = client.post(f"/api/projects/{catalogue}/infer-keys",
                    json={"schema": "aw.yml", "reads_rows": True})
    assert r.status_code == 201, r.text
    assert r.json()["file"]["name"] == "aw.yml"
    assert r.json()["command"].endswith("--source-schema inputs/aw.yml --candidates name "
                                        "--out inputs/aw.yml")
    assert "inferred_keys" in (_inputs(tmp_path, catalogue) / "aw.yml").read_text(encoding="utf-8")
    assert [f["name"] for f in client.get(f"/api/projects/{catalogue}").json()["files"]] == [
        "aw.yml"
    ]


# ── G2 rows are read only when the request says so ────────────────────────────────────────
def test_g2_rows_are_read_only_when_the_request_says_so(
    client: TestClient, catalogue: str, tmp_path: Path,
) -> None:
    before = (_inputs(tmp_path, catalogue) / "aw.yml").read_text(encoding="utf-8")
    for body in ({"schema": "aw.yml"}, {"schema": "aw.yml", "reads_rows": False}):
        r = client.post(f"/api/projects/{catalogue}/infer-keys", json=body)
        assert r.status_code == 422, r.text
        assert "reads rows" in r.text
    assert [p.name for p in _inputs(tmp_path, catalogue).iterdir()] == ["aw.yml"]
    assert (_inputs(tmp_path, catalogue) / "aw.yml").read_text(encoding="utf-8") == before


# ── G3 refusals ───────────────────────────────────────────────────────────────────────────
def test_g3_refusals(client: TestClient, catalogue: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ask = {"schema": "aw.yml", "reads_rows": True}
    r = client.post("/api/projects/nope/infer-keys", json=ask)
    assert r.status_code == 404
    r = client.post(f"/api/projects/{catalogue}/infer-keys", json={**ask, "schema": "other.yml"})
    assert r.status_code == 404 and "other.yml" in r.text
    client.post(f"/api/projects/{catalogue}/files",
                json={"kind": "requirements", "name": "brd.md", "content": "# BRD\n"})
    r = client.post(f"/api/projects/{catalogue}/infer-keys", json={**ask, "schema": "brd.md"})
    assert r.status_code == 422 and "schema" in r.text
    r = client.post(f"/api/projects/{catalogue}/infer-keys", json={**ask, "candidates": "guess"})
    assert r.status_code == 422
    monkeypatch.setenv(ENV, "sqlite://reader:secret@/nowhere.db")
    r = client.post(f"/api/projects/{catalogue}/infer-keys", json=ask)
    assert r.status_code == 502 and "secret" not in r.text
    monkeypatch.delenv(ENV)
    r = client.post(f"/api/projects/{catalogue}/infer-keys", json=ask)
    assert r.status_code == 409 and ENV in r.text


# ── G4 what the database refuses is in the answer ─────────────────────────────────────────
def test_g4_a_refused_column_is_named_in_the_answer(
    client: TestClient, catalogue: str, source: str, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refusing(url: str) -> sa.Engine:
        engine = sa.create_engine(url)

        @sa.event.listens_for(engine, "before_cursor_execute")
        def refuse(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any,
                   executemany: bool) -> None:
            if 'count(DISTINCT main."Routing"."Note")' in statement:
                raise sa.exc.DBAPIError(statement, parameters, UndefinedFunctionError())

        return engine

    monkeypatch.setattr("vault_agent.source_schema_reader.source_engine", refusing)
    r = client.post(f"/api/projects/{catalogue}/infer-keys",
                    json={"schema": "aw.yml", "name": "k.yml", "reads_rows": True})
    assert r.status_code == 201, r.text
    refused = r.json()["refused"]
    assert len(refused) == 1 and refused[0].startswith("main.Routing.Note:"), refused
    # `Routing` is still read: its reference to `Product` is inferred, as without the refusal.
    assert r.json()["summary"] == {"tables": 2, "tables_read": 2, "unique": 1, "foreign": 1}


# ── G5 the pending list says what a key is, as a field ────────────────────────────────────
def test_g5_the_pending_list_carries_the_provenance() -> None:
    state = VaultAgentState(link_proposals=LinkProposals(
        proposals=[LinkProposal(
            source_table="WorkOrder", source_column="ProductID", target_hub="hub_product",
            target_business_key="ProductNumber", category="declared_fk_same_name",
        )],
        relationships=[RelationshipLinkProposal(
            source_table="ProductVendor",
            participations=[
                Participation(referencing_column="ProductID", references_table="Product",
                              references_column="ProductID"),
                Participation(referencing_column="VendorID", references_table="Vendor",
                              references_column="VendorID"),
            ],
        )],
        licenses=[KeyLicense(
            source_table="WorkOrderRouting", source_column="productid",
            references_table="Product", references_column="productid", provenance="inferred",
        )],
    ))
    pending = {entry["key"]: entry for entry in _pending_links(state)}
    assert {key: entry["provenance"] for key, entry in pending.items()} == {
        "WorkOrder.ProductID": "declared",
        "ProductVendor.*": "declared",
        "WorkOrderRouting.productid": "inferred",
    }
