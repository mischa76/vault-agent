"""WP95 — a role-qualified participation reads the relation's foreign-key column that resolves
to its hub (spec §4, C29). Committed red before the change. Keyless; P2 replays the demo's last
step through the deterministic appliers and generator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_wp93_composite_translation import _WP82_BINDINGS
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.orchestrator import apply_human_decision
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.staging_generator import build_staging
from vault_agent.existing_model import stage_aliases
from vault_agent.link_proposal import apply_key_licenses
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)

_DEMO_STATE = (
    Path(__file__).resolve().parents[1] / "demo" / "workbench-adventureworks" / "adventureworks"
    / "runs" / "20261022T234439976097Z" / ".vault-agent" / "state.json"
)
_REMAINING = {
    "stg_work_order_operation", "stg_product_model", "stg_product_subcategory",
    "stg_business_entity_contact",
}


def _hubs() -> list[Hub]:
    return [
        Hub(name="hub_business_entity", business_key="BusinessEntityID",
            source_entity="BusinessEntity", description="A business entity."),
        Hub(name="hub_sales_territory", business_key="TerritoryID",
            source_entity="SalesTerritory", description="A territory."),
    ]


def _sales_person() -> SourceTable:
    return SourceTable(table="SalesPerson", schema="Sales", columns=[
        {"name": "BusinessEntityID", "type": "int"}, {"name": "TerritoryID", "type": "int"},
        {"name": "SalesQuota", "type": "money"},
    ], foreign_keys=[
        {"columns": ["BusinessEntityID"], "references_table": "Employee",
         "references_columns": ["BusinessEntityID"], "references_schema": "HumanResources"},
        {"columns": ["TerritoryID"], "references_table": "SalesTerritory",
         "references_columns": ["TerritoryID"], "references_schema": "Sales"},
    ])


def _store(*, foreign_keys: bool = True) -> SourceTable:
    fks = [
        {"columns": ["BusinessEntityID"], "references_table": "BusinessEntity",
         "references_columns": ["BusinessEntityID"], "references_schema": "Person"},
        {"columns": ["SalesPersonID"], "references_table": "SalesPerson",
         "references_columns": ["BusinessEntityID"], "references_schema": "Sales"},
    ] if foreign_keys else []
    return SourceTable(table="Store", schema="Sales", columns=[
        {"name": "BusinessEntityID", "type": "int"}, {"name": "Name", "type": "nvarchar(50)"},
        {"name": "SalesPersonID", "type": "int"},
    ], foreign_keys=fks)


def _territory_link() -> Link:
    return Link(name="link_sales_person_sales_territory", description="Who sells where.",
                connected_hubs=[LinkHubRef(hub="hub_business_entity", role="sales_person"),
                                "hub_sales_territory"])


def _store_link(*, left: str = "store", right: str = "sales_person") -> Link:
    return Link(name="link_store_sales_person", description="A store and its sales person.",
                connected_hubs=[
                    LinkHubRef(hub="hub_business_entity", role=left, source_key_column="StoreID"),
                    LinkHubRef(hub="hub_business_entity", role=right),
                ])


def _rejected(result_flags: list[object], stage: str) -> bool:
    return any(getattr(f, "kind", None) == FlagKind.BINDING_REJECTED
               and getattr(f, "asset", None) == stage for f in result_flags)


# --- P1 ----------------------------------------------------------------------------------------

def test_one_role_one_foreign_key_into_the_hub_binds_by_rule() -> None:
    model = DVModel(hubs=_hubs(), links=[_territory_link()])
    result = build_staging(model, [_sales_person()],
                           source_overrides={"SALES_PERSON_SALES_TERRITORY": "SalesPerson"})
    meta = result.metadata["stg_sales_person_sales_territory"]
    assert meta["source_binding"] == "declared", meta
    assert meta["source_model"] == {"raw": "SalesPerson"}
    assert meta["derived_columns"] == {"SALES_PERSON_BUSINESSENTITYID": "BUSINESSENTITYID"}
    assert meta["role_columns"] == {"SALES_PERSON_BUSINESSENTITYID": "BUSINESSENTITYID"}
    assert "ratified_columns" not in meta
    assert not _rejected(result.flags, "stg_sales_person_sales_territory")
    expected = meta["expected_source_columns"]
    assert "BUSINESSENTITYID" in expected and "SALES_PERSON_BUSINESSENTITYID" not in expected


def test_two_roles_pair_by_name_and_the_last_by_elimination() -> None:
    model = DVModel(hubs=_hubs(), links=[_store_link()])
    result = build_staging(model, [_store()],
                           source_overrides={"STORE_SALES_PERSON": "Store"})
    meta = result.metadata["stg_store_sales_person"]
    assert meta["source_binding"] == "declared", meta
    assert meta["role_columns"] == {
        "SALES_PERSON_BUSINESSENTITYID": "SALESPERSONID",  # the role names the column
        "STORE_BUSINESSENTITYID": "BUSINESSENTITYID",  # the last role, the last column
    }
    assert meta["derived_columns"]["STORE_BUSINESSENTITYID"] == "BUSINESSENTITYID"
    assert "STOREID" not in json.dumps(meta)  # the modeler's invented alias is gone


def test_the_derived_columns_travel_as_stage_aliases() -> None:
    model = DVModel(hubs=_hubs(), links=[_store_link()])
    result = build_staging(model, [_store()],
                           source_overrides={"STORE_SALES_PERSON": "Store"})
    carried = stage_aliases(result.metadata)
    assert carried["stg_store_sales_person"] == {
        "SALES_PERSON_BUSINESSENTITYID": "SALESPERSONID",
        "STORE_BUSINESSENTITYID": "BUSINESSENTITYID",
    }


def test_a_relation_without_foreign_keys_stays_refused() -> None:
    model = DVModel(hubs=_hubs(), links=[_store_link()])
    result = build_staging(model, [_store(foreign_keys=False)],
                           source_overrides={"STORE_SALES_PERSON": "Store"})
    meta = result.metadata["stg_store_sales_person"]
    assert meta["source_binding"] == "inferred"
    assert _rejected(result.flags, "stg_store_sales_person")


def test_two_unnamed_candidates_for_two_roles_stay_refused() -> None:
    model = DVModel(hubs=_hubs(), links=[_store_link(left="owner", right="manager")])
    result = build_staging(model, [_store()],
                           source_overrides={"STORE_SALES_PERSON": "Store"})
    meta = result.metadata["stg_store_sales_person"]
    assert meta["source_binding"] == "inferred"
    assert "role_columns" not in meta


# --- P2: the demo's last step ---------------------------------------------------------------

async def _replayed() -> VaultAgentState:
    state = VaultAgentState.model_validate_json(_DEMO_STATE.read_text(encoding="utf-8"))
    ex = state.existing_model
    delta = DVModel(
        hubs=[h for h in state.dv_model.hubs if h.name not in {x.name for x in ex.hubs}],
        links=[lk for lk in state.dv_model.links if lk.name not in {x.name for x in ex.links}],
        satellites=[s for s in state.dv_model.satellites
                    if s.name not in {x.name for x in ex.satellites}],
    )
    repaired = apply_key_licenses(delta, ex, state)
    by_name = {lk.name: lk for lk in repaired.links}
    state.dv_model.links = [by_name.get(lk.name, lk) for lk in state.dv_model.links]
    state.flags = [f for f in state.flags
                   if f.kind not in ("source_binding", "binding_rejected", "link_binding_evidence")]
    state = await CodeGeneratorAgent().run(state)
    rebind_staging(state)
    return state


def _inferred(state: VaultAgentState) -> list[str]:
    staging = state.artifacts.automatedv_yaml["staging"]
    return sorted(n for n, m in staging.items() if m.get("source_binding") == "inferred")


@pytest.mark.skipif(not _DEMO_STATE.is_file(), reason="the shipped demo is not checked out")
async def test_the_demo_s_last_step_needs_four_bindings_not_seven() -> None:
    state = await _replayed()
    assert set(_inferred(state)) == _REMAINING, _inferred(state)
    apply_human_decision(state, {"bindings": {
        k: v for k, v in json.loads(json.dumps(_WP82_BINDINGS)).items() if k in _REMAINING
    }})
    assert _inferred(state) == []
    meta = state.artifacts.automatedv_yaml["staging"]["stg_store_sales_person"]
    # The sales person's column came from the ratified license (WP41's applier aliases it);
    # the rule derived the one the license could not — the invented `StoreID`.
    assert meta["role_columns"] == {"STORE_BUSINESSENTITYID": "BUSINESSENTITYID"}
    assert meta["derived_columns"]["SALES_PERSON_BUSINESSENTITYID"] == "SALESPERSONID"
    assert "STOREID" not in json.dumps(meta)
