"""WP45 — composite business keys, typed from the modeler to the hash (spec §3).

Committed before the change, failing. Every assertion branches on typed fields and generated
text the warehouse reads; the shape is the FK-links demo's ``CurrencyRate`` miniature.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from vault_agent import llm
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent, _tool_schema
from vault_agent.agents.staging_generator import collect_staging_specs
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import hub_key_columns
from vault_agent.state import (
    DVModel,
    Hub,
    HubSource,
    Link,
    LinkHubRef,
    Satellite,
    SourceTable,
    VaultAgentState,
)

RATE_COLUMNS = ["CurrencyRateDate", "FromCurrencyCode", "ToCurrencyCode"]
RATE_NORMALISED = ["CURRENCYRATEDATE", "FROMCURRENCYCODE", "TOCURRENCYCODE"]


def _currency() -> Hub:
    return Hub(name="hub_currency", business_key="CurrencyCode", source_entity="Currency",
               description="A currency.")


def _rate(columns: list[str] | None = RATE_COLUMNS) -> Hub:
    return Hub(name="hub_currency_rate", business_key="currency rate key",
               business_key_columns=list(columns or []), source_entity="CurrencyRate",
               description="An exchange rate for a day and a currency pair.")


def _rate_sat() -> Satellite:
    return Satellite(name="sat_currency_rate_detail", parent="hub_currency_rate",
                     attributes=["AverageRate", "EndOfDayRate"], source_table="CurrencyRate",
                     description="The rates of the day.")


def _rate_link() -> Link:
    return Link(
        name="link_currency_rate_currencies",
        connected_hubs=[
            "hub_currency_rate",
            LinkHubRef(hub="hub_currency", role="from", source_key_column="FromCurrencyCode"),
            LinkHubRef(hub="hub_currency", role="to", source_key_column="ToCurrencyCode"),
        ],
        description="Which two currencies a rate converts between.",
    )


def _model() -> DVModel:
    return DVModel(hubs=[_currency(), _rate()], links=[_rate_link()], satellites=[_rate_sat()])


def _schema(rate_columns: list[str] | None = None) -> list[SourceTable]:
    return [
        SourceTable(table="Currency", columns=["CurrencyCode", "Name"]),
        SourceTable(table="CurrencyRate", columns=(rate_columns or RATE_COLUMNS)
                    + ["AverageRate", "EndOfDayRate"]),
    ]


def _codes(state: VaultAgentState, code: str) -> list[str]:
    return [i.message for i in state.validation_report.issues if i.code == code]


# --- Guard 1: the helper and the schema ---------------------------------------------------


def test_hub_key_columns_is_single_for_todays_hubs_and_the_list_for_composite() -> None:
    assert hub_key_columns(_currency()) == ["CURRENCYCODE"]
    assert hub_key_columns(_rate()) == RATE_NORMALISED
    assert hub_key_columns(_rate(columns=[])) == ["CURRENCY_RATE_KEY"]  # label, as today


def test_the_modeler_tool_schema_exposes_business_key_columns() -> None:
    schema = json.dumps(_tool_schema())
    assert "business_key_columns" in schema


# --- Guard 2: staging hashes the list -----------------------------------------------------


def test_composite_hub_stage_hashes_every_column_and_passes_them_through() -> None:
    specs = collect_staging_specs(_model())
    hub_stage = specs["stg_currency_rate"]
    assert ("CURRENCYRATE_HK", RATE_NORMALISED) in hub_stage.hashed
    assert all(col in hub_stage.source_columns for col in RATE_NORMALISED)

    sat_stage = specs["stg_currency_rate_detail"]
    assert ("CURRENCYRATE_HK", RATE_NORMALISED) in sat_stage.hashed
    assert all(col in sat_stage.source_columns for col in RATE_NORMALISED)


def test_a_link_with_a_composite_participant_hashes_it_over_the_list() -> None:
    specs = collect_staging_specs(_model())
    link_stage = specs["stg_currency_rate_currencies"]
    hashed = dict(link_stage.hashed)
    assert hashed["CURRENCYRATE_HK"] == RATE_NORMALISED
    assert hashed["FROM_CURRENCY_HK"] == "FROM_CURRENCYCODE"
    assert hashed["TO_CURRENCY_HK"] == "TO_CURRENCYCODE"
    assert hashed["LINK_CURRENCY_RATE_CURRENCIES_HK"] == (
        RATE_NORMALISED + ["FROM_CURRENCYCODE", "TO_CURRENCYCODE"]
    )


# --- Guard 3: the hub's natural key is the list ------------------------------------------


async def test_hub_renders_a_list_src_nk_and_single_key_hubs_are_unchanged() -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(dv_model=_model()))
    rate_sql = state.artifacts.dbt_models["hub_currency_rate"]
    assert (
        '{%- set src_nk = ["CURRENCYRATEDATE", "FROMCURRENCYCODE", "TOCURRENCYCODE"] -%}'
        in rate_sql
    )
    assert '{%- set src_nk = "CURRENCYCODE" -%}' in state.artifacts.dbt_models["hub_currency"]
    meta = state.artifacts.automatedv_yaml["hubs"]["hub_currency_rate"]
    assert meta["src_nk"] == RATE_NORMALISED


# --- Guard 4: the gates read the list ----------------------------------------------------


async def test_sat_key_gate_is_silent_when_the_relation_carries_every_column() -> None:
    state = VaultAgentState(dv_model=_model(), source_schemas=_schema())
    await ValidatorAgent().run(state)
    assert _codes(state, "E_SAT_KEY_NOT_IN_SOURCE") == []
    assert _codes(state, "W_BK_NOT_IN_SOURCE") == []
    assert _codes(state, "E_HUB_COMPOSITE_UNSUPPORTED") == []


async def test_sat_key_gate_names_the_missing_column_of_a_composite_key() -> None:
    state = VaultAgentState(
        dv_model=_model(),
        source_schemas=_schema(rate_columns=["CurrencyRateDate", "FromCurrencyCode"]),
    )
    await ValidatorAgent().run(state)
    [sat_msg] = _codes(state, "E_SAT_KEY_NOT_IN_SOURCE")
    assert "TOCURRENCYCODE" in sat_msg and "CURRENCYRATEDATE" not in sat_msg
    [bk_msg] = _codes(state, "W_BK_NOT_IN_SOURCE")
    assert "TOCURRENCYCODE" in bk_msg and "currency rate key" not in bk_msg


async def test_composite_key_on_one_entity_still_collides_with_a_single_key() -> None:
    other = Hub(name="hub_currency_rate_id", business_key="CurrencyRateID",
                source_entity="CurrencyRate", description="The rate's surrogate.")
    state = VaultAgentState(dv_model=DVModel(hubs=[_rate(), other]))
    await ValidatorAgent().run(state)
    assert len(_codes(state, "E_HUB_HK_COLLISION")) == 1


async def test_unsupported_composite_shapes_are_refused_not_staged() -> None:
    multi = _rate()
    multi.sources = [
        HubSource(source_table="CurrencyRate", business_key_column="CurrencyRateDate"),
        HubSource(source_table="CurrencyRateArchive", business_key_column="RateDate"),
    ]
    state = VaultAgentState(dv_model=DVModel(hubs=[multi]))
    await ValidatorAgent().run(state)
    [msg] = _codes(state, "E_HUB_COMPOSITE_UNSUPPORTED")
    assert "multi-source" in msg

    role_link = Link(
        name="link_rate_pair",
        connected_hubs=[LinkHubRef(hub="hub_currency_rate", role="base"), "hub_currency"],
        description="A rate in a role.",
    )
    state = VaultAgentState(dv_model=DVModel(hubs=[_currency(), _rate()], links=[role_link]))
    await ValidatorAgent().run(state)
    [msg] = _codes(state, "E_HUB_COMPOSITE_UNSUPPORTED")
    assert "role" in msg and "link_rate_pair" in msg


# --- Guard 5: the backstop for the modeler's notation ------------------------------------


def _payload(business_key: str, columns: list[str] | None = None) -> dict:
    hub = {"name": "hub_currency_rate", "business_key": business_key,
           "source_entity": "CurrencyRate", "description": "A rate."}
    if columns is not None:
        hub["business_key_columns"] = columns
    return {"hubs": [hub], "links": [], "satellites": []}


def _split(payload: dict, state: VaultAgentState) -> tuple[Hub, list[llm.TraceEvent]]:
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        model = Dv2ModelerAgent()._validate_model(payload, state)
    finally:
        llm.set_trace_recorder(None)
    return model.hubs[0], [e for e in events if e.kind == "backstop"]


def test_backstop_splits_a_plus_joined_key_when_every_part_is_declared() -> None:
    hub, events = _split(_payload(" + ".join(RATE_COLUMNS)),
                         VaultAgentState(source_schemas=_schema()))
    assert hub.business_key_columns == RATE_COLUMNS
    assert hub.business_key == " + ".join(RATE_COLUMNS)  # the label is kept
    assert [e.backstop_id for e in events] == ["composite_key_split"]
    assert events[0].detail["columns"] == RATE_COLUMNS


def test_backstop_is_inert_without_a_schema_an_undeclared_part_or_set_columns() -> None:
    joined = " + ".join(RATE_COLUMNS)
    hub, events = _split(_payload(joined), VaultAgentState())
    assert hub.business_key_columns == [] and events == []

    hub, events = _split(_payload("CurrencyRateDate + Nonsense"),
                         VaultAgentState(source_schemas=_schema()))
    assert hub.business_key_columns == [] and events == []

    hub, events = _split(_payload(joined, columns=["CurrencyRateDate", "ToCurrencyCode"]),
                         VaultAgentState(source_schemas=_schema()))
    assert hub.business_key_columns == ["CurrencyRateDate", "ToCurrencyCode"] and events == []


# --- Guard 6: the demo builder carries the composite shape --------------------------------


_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "fk_links_postgres" / "build_vault_models.py"
)


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wp45_fk_links_builder", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_the_fk_links_demo_builds_a_composite_hub_its_satellite_and_a_link() -> None:
    builder = _load_builder()
    state = await builder.build_state()
    [rate] = [h for h in state.dv_model.hubs if h.name == "hub_currency_rate"]
    assert rate.business_key_columns == RATE_COLUMNS
    assert "sat_currency_rate_detail" in state.artifacts.dbt_models
    assert "link_currency_rate_currencies" in state.artifacts.dbt_models
    assert '{%- set src_nk = ["CURRENCYRATEDATE", "FROMCURRENCYCODE", "TOCURRENCYCODE"] -%}' in (
        state.artifacts.dbt_models["hub_currency_rate"]
    )
    assert not any(i.severity == "error" for i in state.validation_report.issues)
