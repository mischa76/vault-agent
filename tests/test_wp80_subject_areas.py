"""WP80 — the Model perspective shows the vault by subject area (spec §3). Committed before the
change, failing. Keyless: the areas are a reading of the model, the catalogue and the staging
bindings; the API test runs the stub pipeline with a model planted by one stub agent."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_cli import _sqlite_stub_agents
from tests.test_wp66_workbench_api import _REQUIREMENTS
from vault_agent import cli
from vault_agent.agents.staging_generator import build_staging
from vault_agent.graph import build_graph
from vault_agent.report import build_model_mermaid
from vault_agent.state import DVModel, SourceTable, VaultAgentState
from vault_agent.subject_areas import NO_SCHEMA_AREA, UNBOUND_AREA, subject_areas
from vault_agent.ui.app import create_app

CUSTOMER = SourceTable(table="Customer", schema="crm", columns=["CustomerID", "Name"])
ACCOUNT = SourceTable(table="Account", schema="fin", columns=["AccountNo", "Balance"])
ACCOUNT_CUSTOMER = SourceTable(
    table="AccountCustomer", schema="fin", columns=["AccountNo", "CustomerID"]
)
TABLES = [CUSTOMER, ACCOUNT, ACCOUNT_CUSTOMER]


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
             "description": "c"},
            {"name": "hub_account", "business_key": "AccountNo", "source_entity": "Account",
             "description": "a"},
        ],
        "links": [
            {"name": "link_account_customer", "connected_hubs": ["hub_account", "hub_customer"],
             "description": "holds"},
            # Never bound: no relation of that name is declared anywhere.
            {"name": "link_customer_region", "connected_hubs": ["hub_customer"],
             "description": "lives in"},
        ],
        "satellites": [
            {"name": "sat_customer_details", "parent": "hub_customer", "attributes": ["Name"],
             "description": "d"},
            {"name": "sat_account_details", "parent": "hub_account", "attributes": ["Balance"],
             "description": "d"},
        ],
    })


def _by_name(areas: list[Any]) -> dict[str, Any]:
    return {a.name: a for a in areas}


# ── §3.1 the partition ─────────────────────────────────────────────────────────────────────
def test_areas_are_the_schemas_of_what_each_construct_reads() -> None:
    model = _model()
    areas = subject_areas(model, TABLES)
    assert [a.name for a in areas] == ["crm", "fin", UNBOUND_AREA]
    crm, fin, unbound = areas
    assert (crm.hubs, crm.links, crm.satellites) == (["hub_customer"], [], ["sat_customer_details"])
    assert crm.neighbours == []
    assert (fin.hubs, fin.links, fin.satellites) == (
        ["hub_account"], ["link_account_customer"], ["sat_account_details"]
    )
    assert fin.neighbours == ["hub_customer"]
    assert (unbound.hubs, unbound.links, unbound.satellites) == ([], ["link_customer_region"], [])
    assert unbound.neighbours == ["hub_customer"]
    assert [a.increment for a in areas] == [True, True, False]


def test_the_staging_metadata_and_the_recomputation_agree() -> None:
    model = _model()
    staging = build_staging(model, TABLES).metadata
    from_metadata = subject_areas(model, TABLES, staging=staging)
    recomputed = subject_areas(model, TABLES)
    assert [(a.name, a.hubs, a.links, a.satellites, a.neighbours) for a in from_metadata] == [
        (a.name, a.hubs, a.links, a.satellites, a.neighbours) for a in recomputed
    ]


def test_tables_without_a_schema_form_one_area() -> None:
    model = _model()
    bare = [SourceTable(table=t.table, columns=list(t.column_names)) for t in TABLES]
    areas = subject_areas(model, bare)
    assert [a.name for a in areas] == [NO_SCHEMA_AREA, UNBOUND_AREA]
    assert set(areas[0].hubs) == {"hub_customer", "hub_account"}


def test_the_increment_is_the_run_s_own_tables() -> None:
    """Carried tables (WP74) bind the same way; only `source_schemas` makes an area the increment's."""
    model = _model()
    areas = _by_name(subject_areas(model, [ACCOUNT, ACCOUNT_CUSTOMER], carried=[CUSTOMER]))
    assert areas["fin"].increment and not areas["crm"].increment
    assert areas["crm"].hubs == ["hub_customer"]


# ── §3.2 multi-source hubs and their satellites ────────────────────────────────────────────
def test_a_multi_source_hub_belongs_to_every_feed_s_area() -> None:
    model = DVModel.model_validate({
        "hubs": [{"name": "hub_party", "business_key": "PartyID", "source_entity": "Party",
                  "description": "p", "sources": [
                      {"source_table": "Customer", "business_key_column": "CustomerID"},
                      {"source_table": "Account", "business_key_column": "AccountNo"}]}],
        "links": [],
        "satellites": [
            {"name": "sat_party_account", "parent": "hub_party", "attributes": ["Balance"],
             "source_table": "Account", "description": "feed-bound"},
            {"name": "sat_party_details", "parent": "hub_party", "attributes": ["Name"],
             "description": "one per feed"},
        ],
    })
    areas = _by_name(subject_areas(model, TABLES))
    assert set(areas) == {"crm", "fin"}
    assert areas["crm"].hubs == ["hub_party"] and areas["fin"].hubs == ["hub_party"]
    assert areas["fin"].satellites == ["sat_party_account", "sat_party_details"]
    assert areas["crm"].satellites == ["sat_party_details"]
    assert areas["crm"].neighbours == [] and areas["fin"].neighbours == []


# ── §3.3 the scoped Mermaid ────────────────────────────────────────────────────────────────
def test_the_scoped_diagram_shows_members_and_dashed_neighbours() -> None:
    model = _model()
    fin = _by_name(subject_areas(model, TABLES))["fin"]
    mer = build_model_mermaid(model, members=fin.members(), neighbours=fin.neighbours)
    assert mer.startswith("flowchart LR")
    assert "HUB_ACCOUNT[" in mer and "LINK_ACCOUNT_CUSTOMER{{" in mer and "SAT_ACCOUNT_DETAILS(" in mer
    assert "HUB_CUSTOMER[" in mer and "  class HUB_CUSTOMER neighbour;" in mer
    assert "  LINK_ACCOUNT_CUSTOMER --> HUB_ACCOUNT" in mer
    assert "  LINK_ACCOUNT_CUSTOMER --> HUB_CUSTOMER" in mer
    assert "SAT_CUSTOMER_DETAILS" not in mer and "LINK_CUSTOMER_REGION" not in mer
    # Unscoped: byte-identical to before — no neighbour class is declared.
    assert "neighbour" not in build_model_mermaid(model)


# ── §3.4 the API ───────────────────────────────────────────────────────────────────────────
_SCHEMA = """source_schemas:
  - table: Customer
    schema: crm
    columns: [CustomerID, Name]
  - table: Account
    schema: fin
    columns: [AccountNo, Balance]
  - table: AccountCustomer
    schema: fin
    columns: [AccountNo, CustomerID]
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    agents = _sqlite_stub_agents(block_signoff=True)
    modeler = agents["dv2_modeler"]

    class _Modeler:
        async def run(self, state: VaultAgentState) -> VaultAgentState:
            state.dv_model = _model()
            return await modeler.run(state)  # type: ignore[attr-defined]

    agents["dv2_modeler"] = _Modeler()
    monkeypatch.setattr(cli, "build_graph", lambda: build_graph(agents))  # type: ignore[arg-type]
    return TestClient(create_app(tmp_path / "projects"))


def test_the_model_response_carries_the_areas(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    client.post(f"/api/projects/{pid}/files",
                json={"kind": "requirements", "name": "req.md", "content": _REQUIREMENTS})
    client.post(f"/api/projects/{pid}/files",
                json={"kind": "schema", "name": "schema.yml", "content": _SCHEMA})
    run = client.post(f"/api/projects/{pid}/runs?wait=true",
                      json={"requirements": "req.md", "schema": "schema.yml"}).json()
    view = client.get(f"/api/runs/{run['id']}/model").json()
    areas = view["areas"]
    assert [a["name"] for a in areas] == ["crm", "fin", UNBOUND_AREA]
    constructs = {c["name"] for kind in ("hubs", "links", "satellites") for c in view["model"][kind]}
    covered = {n for a in areas for kind in ("hubs", "links", "satellites") for n in a[kind]}
    assert covered == constructs
    assert all(a["mermaid"].startswith("flowchart") for a in areas)
    assert "class HUB_CUSTOMER neighbour;" in areas[1]["mermaid"]
    assert view["output_mermaid"].startswith("flowchart")  # the whole model stays
