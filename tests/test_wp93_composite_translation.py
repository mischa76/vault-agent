"""WP93 — composite-key translation (spec §4, C28). Committed red before the change, on the
miniature of the paid chain's last hand view: `SalesOrderHeader.CurrencyRateID → CurrencyRate`,
`hub_currency_rate` keyed on three columns. Keyless; P3 replays the stored state of the demo's
last step through the deterministic appliers and generator."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.orchestrator import apply_human_decision, apply_link_decision
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.staging_generator import build_staging, zero_key_hubs
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import (
    apply_key_licenses,
    collect_link_proposals,
    propose_links,
)
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    DVModel,
    Hub,
    KeyTranslation,
    Link,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)

RATE_COLUMNS = ["CurrencyRateDate", "FromCurrencyCode", "ToCurrencyCode"]
RATE_NORMALISED = ["CURRENCYRATEDATE", "FROMCURRENCYCODE", "TOCURRENCYCODE"]
_DEMO_STATE = (
    Path(__file__).resolve().parents[1] / "demo" / "workbench-adventureworks" / "adventureworks"
    / "runs" / "20261022T234439976097Z" / ".vault-agent" / "state.json"
)
_WP82_BINDINGS = {
    "stg_work_order_operation": {"relation": "WorkOrderRouting"},
    "stg_product_model": {"relation": "Product"},
    "stg_product_subcategory": {"relation": "Product"},
    "stg_business_entity_contact": {"relation": "BusinessEntityContact", "columns": {
        "ORGANISATION_BUSINESSENTITYID": "BusinessEntityID",
        "CONTACT_PERSON_BUSINESSENTITYID": "PersonID"}},
    "stg_sales_person_sales_territory": {"relation": "SalesPerson", "columns": {
        "SALES_PERSON_BUSINESSENTITYID": "BusinessEntityID"}},
    "stg_sales_person_territory_history": {"relation": "SalesTerritoryHistory", "columns": {
        "SALES_PERSON_BUSINESSENTITYID": "BusinessEntityID"}},
    "stg_store_sales_person": {"relation": "Store", "columns": {
        "STOREID": "BusinessEntityID", "SALES_PERSON_BUSINESSENTITYID": "SalesPersonID"}},
}


def _rate_table() -> SourceTable:
    return SourceTable(table="CurrencyRate", schema="Sales", columns=[
        {"name": "CurrencyRateID", "type": "int"},
        {"name": "CurrencyRateDate", "type": "datetime"},
        {"name": "FromCurrencyCode", "type": "nchar(3)"},
        {"name": "ToCurrencyCode", "type": "nchar(3)"},
        {"name": "AverageRate", "type": "money"},
    ])


def _header_table() -> SourceTable:
    return SourceTable(table="SalesOrderHeader", schema="Sales", columns=[
        {"name": "SalesOrderID", "type": "int"},
        {"name": "SalesOrderNumber", "type": "nvarchar(25)"},
        {"name": "CurrencyRateID", "type": "int"},
        {"name": "TotalDue", "type": "money"},
    ], foreign_keys=[{
        "columns": ["CurrencyRateID"], "references_table": "CurrencyRate",
        "references_columns": ["CurrencyRateID"], "references_schema": "Sales",
    }])


def _rate_hub() -> Hub:
    return Hub(name="hub_currency_rate", business_key="currency rate key",
               business_key_columns=RATE_COLUMNS, source_entity="CurrencyRate",
               description="An exchange rate for a day and a currency pair.")


def _order_hub() -> Hub:
    return Hub(name="hub_sales_order", business_key="SalesOrderNumber",
               source_entity="SalesOrderHeader", description="A sales order.")


def _translation() -> KeyTranslation:
    return KeyTranslation(referencing_column="CurrencyRateID", through_table="CurrencyRate",
                          through_schema="Sales", surrogate_column="CurrencyRateID",
                          natural_key_column="CURRENCYRATEDATE",
                          natural_key_columns=RATE_NORMALISED)


def _link(ref: LinkHubRef | None = None) -> Link:
    return Link(name="link_sales_order", description="The order with its currency rate.",
                connected_hubs=["hub_sales_order", ref or LinkHubRef(hub="hub_currency_rate")])


def _ratified_state() -> tuple[VaultAgentState, DVModel]:
    """The license ratified, the applier run against the modeler's delta (greenfield path)."""
    state = VaultAgentState(source_schemas=[_header_table(), _rate_table()])
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    delta = DVModel(hubs=[_order_hub(), _rate_hub()], links=[_link()])
    merged = apply_key_licenses(delta, DVModel(), state)
    state.dv_model = merged
    return state, merged


def _rate_ref(model: DVModel) -> LinkHubRef:
    [link] = [lk for lk in model.links if lk.name == "link_sales_order"]
    return next(ref for ref in link.hub_refs if ref.hub == "hub_currency_rate")


# --- P1: trigger, applier, gate ---------------------------------------------------------------

def test_a_surrogate_into_a_composite_hub_is_a_translated_proposal() -> None:
    proposals, skipped = propose_links(
        DVModel(hubs=[_rate_hub()]), [_header_table(), _rate_table()]
    )
    assert skipped == [], [(s.asset, s.reason, s.message) for s in skipped]
    [p] = proposals.proposals
    assert (p.target_hub, p.category) == ("hub_currency_rate", "declared_fk_translated")
    assert p.translation is not None
    assert p.translation.natural_key_columns == RATE_NORMALISED
    assert p.translation.through_table == "CurrencyRate"


def test_a_declared_through_relation_missing_one_key_column_is_the_typed_skip() -> None:
    rate = SourceTable(table="CurrencyRate", schema="Sales",
                       columns=["CurrencyRateID", "CurrencyRateDate", "FromCurrencyCode"])
    proposals, skipped = propose_links(DVModel(hubs=[_rate_hub()]), [_header_table(), rate])
    assert proposals.proposals == []
    [s] = skipped
    assert s.reason == "translation_key_missing" and "ToCurrencyCode" in s.message


def test_the_ratified_license_resolves_and_repairs_the_modeler_s_link() -> None:
    state, merged = _ratified_state()
    [lic] = state.link_proposals.licenses
    assert lic.resolved_by_applier and lic.target_hub == "hub_currency_rate"
    assert lic.key_translation is not None
    assert lic.key_translation.natural_key_columns == RATE_NORMALISED
    ref = _rate_ref(merged)
    assert ref.key_translation is not None and ref.source_key_column is None
    assert ref.key_translation.natural_key_columns == RATE_NORMALISED


async def test_the_gate_admits_the_translation_and_still_refuses_a_role() -> None:
    state, _ = _ratified_state()
    report = (await ValidatorAgent().run(state)).validation_report
    refused = {"E_HUB_COMPOSITE_UNSUPPORTED", "E_LINK_TRANSLATION_UNRATIFIED",
               "E_LINK_KEY_NOT_IN_SOURCE"}
    assert not [i for i in report.issues if i.code in refused], [
        (i.code, i.message) for i in report.issues
    ]
    role = VaultAgentState(source_schemas=[_header_table(), _rate_table()], dv_model=DVModel(
        hubs=[_order_hub(), _rate_hub()],
        links=[_link(LinkHubRef(hub="hub_currency_rate", role="billing"))],
    ))
    report = (await ValidatorAgent().run(role)).validation_report
    assert [i for i in report.issues if i.code == "E_HUB_COMPOSITE_UNSUPPORTED"]


# --- P2: staging ---------------------------------------------------------------------------

def _model() -> DVModel:
    ref = LinkHubRef(hub="hub_currency_rate", key_translation=_translation())
    return DVModel(hubs=[_order_hub(), _rate_hub()], links=[_link(ref)])


def test_the_translation_view_projects_every_key_column_and_the_stage_hashes_them() -> None:
    result = build_staging(_model(), [_header_table(), _rate_table()])
    via = "stg_sales_order_via_currencyrate"
    assert via in result.models, sorted(result.models)
    sql = result.models[via]
    assert sql.count("left join") == 1
    for column in RATE_NORMALISED:
        assert f"r.{column} as {column}" in sql
    assert "on t.CURRENCYRATEID = r.CURRENCYRATEID" in sql
    stage = result.models["stg_sales_order"]
    assert f"source_model: '{via}'" in stage
    hashed = result.metadata["stg_sales_order"]["hashed_columns"]
    assert isinstance(hashed, dict)
    assert hashed["CURRENCYRATE_HK"] == RATE_NORMALISED
    assert hashed["SALESORDERHEADER_HK"] == "SALESORDERNUMBER"  # the hub's own key, untouched
    # the hub's own stage hashes the same three columns from CurrencyRate itself
    rate_hashed = result.metadata["stg_currency_rate"]["hashed_columns"]
    assert isinstance(rate_hashed, dict) and rate_hashed["CURRENCYRATE_HK"] == RATE_NORMALISED


def test_a_null_surrogate_is_a_null_participant_not_a_dangling_reference() -> None:
    result = build_staging(_model(), [_header_table(), _rate_table()])
    yml = result.scaffolding["models/staging/stg_sales_order_via_currencyrate.yml"]
    assert yml.count("- not_null") == 3 and "relationships" in yml
    assert "CURRENCYRATEID is not null" in yml
    meta = result.metadata["stg_sales_order"]
    optional = meta.get("null_columns", {})
    assert isinstance(optional, dict)
    assert set(RATE_NORMALISED) <= set(optional.get("optional", [])), meta.get("null_columns")
    assert "hub_currency_rate" in result.zero_key_hubs


def test_zero_key_types_for_a_translated_participation_come_from_the_through_relation() -> None:
    from vault_agent.agents.staging_generator import collect_staging_specs

    model = _model()
    schemas = [_header_table(), _rate_table()]
    result = build_staging(model, schemas)
    assert "stg_currency_rate_zero_keys" in result.models
    specs = collect_staging_specs(model)
    declared = {normalize_identifier(t.table): t for t in schemas}
    from vault_agent.agents.staging_generator import bind_sources
    bind_sources(specs, schemas)
    typed = zero_key_hubs(model, specs, declared)
    assert [c for c, _ in typed["hub_currency_rate"]] == RATE_NORMALISED
    assert [t for _, t in typed["hub_currency_rate"]] == ["varchar", "varchar", "varchar"]


# --- P3: the paid chain's last step, replayed ------------------------------------------------

@pytest.mark.skipif(not _DEMO_STATE.is_file(), reason="the shipped demo is not checked out")
async def test_the_demo_s_last_step_needs_no_hand_view_any_more() -> None:
    state = VaultAgentState.model_validate_json(_DEMO_STATE.read_text(encoding="utf-8"))
    existing_names = {h.name for h in state.existing_model.hubs}
    link_names = {lk.name for lk in state.existing_model.links}
    sat_names = {s.name for s in state.existing_model.satellites}
    delta = DVModel(
        hubs=[h for h in state.dv_model.hubs if h.name not in existing_names],
        links=[lk for lk in state.dv_model.links if lk.name not in link_names],
        satellites=[s for s in state.dv_model.satellites if s.name not in sat_names],
    )
    [lic] = [x for x in state.link_proposals.licenses
             if (x.source_table, x.source_column) == ("SalesOrderHeader", "CurrencyRateID")]
    assert not lic.resolved_by_applier  # as the paid run left it
    repaired = apply_key_licenses(delta, state.existing_model, state)
    assert lic.resolved_by_applier and lic.target_hub == "hub_currency_rate"
    ref = _rate_ref(repaired)
    assert ref.key_translation is not None
    assert ref.key_translation.natural_key_columns == RATE_NORMALISED
    by_name = {lk.name: lk for lk in repaired.links}
    state.dv_model.links = [by_name.get(lk.name, lk) for lk in state.dv_model.links]
    state.flags = [f for f in state.flags
                   if f.kind not in ("source_binding", "binding_rejected", "link_binding_evidence")]
    state = await CodeGeneratorAgent().run(state)
    rebind_staging(state)
    apply_human_decision(state, {"bindings": json.loads(json.dumps(_WP82_BINDINGS))})
    staging = state.artifacts.automatedv_yaml["staging"]
    inferred = sorted(n for n, m in staging.items() if m.get("source_binding") == "inferred")
    assert inferred == [], inferred
    assert "stg_sales_order_via_currencyrate" in state.artifacts.staging_models
