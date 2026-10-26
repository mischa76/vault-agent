"""WP94 — an optional participation whose hub cannot be zero-keyed is a link of its own (spec §4,
C30). Committed red before the change: the gate, its two severities, its remedy; the demo's last
step replayed. Keyless."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_wp93_composite_translation import (
    RATE_NORMALISED,
    _rate_hub,
    _rate_table,
    _translation,
)
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import apply_key_licenses
from vault_agent.state import (
    ColumnProfile,
    DVModel,
    Hub,
    Link,
    LinkHubRef,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)

ERROR, WARNING = "E_LINK_OPTIONAL_PARTICIPANT", "W_LINK_OPTIONAL_PARTICIPANT"
_DEMO_STATE = (
    Path(__file__).resolve().parents[1] / "demo" / "workbench-adventureworks" / "adventureworks"
    / "runs" / "20261022T234439976097Z" / ".vault-agent" / "state.json"
)


def _header(nullable: bool | None) -> SourceTable:
    rate = {"name": "CurrencyRateID", "type": "int"}
    if nullable is not None:
        rate["nullable"] = nullable
    return SourceTable(table="SalesOrderHeader", schema="Sales", columns=[
        {"name": "SalesOrderNumber", "type": "nvarchar(25)"},
        {"name": "CustomerID", "type": "int"},
        rate,
    ], foreign_keys=[{
        "columns": ["CurrencyRateID"], "references_table": "CurrencyRate",
        "references_columns": ["CurrencyRateID"], "references_schema": "Sales",
    }])


def _hubs() -> list[Hub]:
    return [
        Hub(name="hub_sales_order_header", business_key="SalesOrderNumber",
            source_entity="SalesOrderHeader", description="A sales order."),
        Hub(name="hub_customer", business_key="CustomerID", source_entity="Customer",
            description="A customer."),
        _rate_hub(),
    ]


def _link(*, with_rate: bool = True) -> Link:
    hubs: list[str | LinkHubRef] = ["hub_sales_order_header", "hub_customer"]
    if with_rate:
        hubs.append(LinkHubRef(hub="hub_currency_rate", key_translation=_translation()))
    return Link(name="link_sales_order_header", description="The order with its parties.",
                connected_hubs=hubs)


def _state(nullable: bool | None, *, profile: float | None = None,
           with_rate: bool = True) -> VaultAgentState:
    state = VaultAgentState(
        dv_model=DVModel(hubs=_hubs(), links=[_link(with_rate=with_rate)]),
        source_schemas=[
            _header(nullable), _rate_table(),
            SourceTable(table="Customer", columns=[{"name": "CustomerID", "type": "int"}]),
        ],
    )
    if profile is not None:
        state.profiling = {"SalesOrderHeader": {
            "CurrencyRateID": ColumnProfile(name="CurrencyRateID", null_ratio=profile)}}
    return state


async def _codes(state: VaultAgentState) -> dict[str, list[str]]:
    report = (await ValidatorAgent().run(state)).validation_report
    out: dict[str, list[str]] = {}
    for issue in report.issues:
        if issue.code in (ERROR, WARNING):
            out.setdefault(issue.code, []).append(issue.remedy or "")
    return out


# --- P1 ----------------------------------------------------------------------------------------

async def test_a_nullable_surrogate_into_a_datetime_keyed_hub_is_refused() -> None:
    codes = await _codes(_state(nullable=True))
    assert list(codes) == [ERROR], codes
    [remedy] = codes[ERROR]
    assert "link_sales_order_header_currency_rate" in remedy
    assert "hub_currency_rate" in remedy and "hub_sales_order_header" in remedy
    assert "hub_customer" not in remedy


async def test_without_evidence_of_nullability_it_is_a_warning_with_the_same_remedy() -> None:
    codes = await _codes(_state(nullable=None))
    assert list(codes) == [WARNING], codes
    assert "link_sales_order_header_currency_rate" in codes[WARNING][0]


async def test_a_profile_with_nulls_is_evidence() -> None:
    codes = await _codes(_state(nullable=None, profile=0.55))
    assert list(codes) == [ERROR], codes


async def test_a_column_declared_not_nullable_raises_nothing() -> None:
    assert await _codes(_state(nullable=False)) == {}
    assert await _codes(_state(nullable=None, profile=0.0)) == {}


async def test_a_two_hub_link_raises_nothing() -> None:
    state = _state(nullable=True)
    state.dv_model.links = [Link(
        name="link_sales_order_header_currency_rate", description="The order's rate.",
        connected_hubs=["hub_sales_order_header",
                        LinkHubRef(hub="hub_currency_rate", key_translation=_translation())],
    )]
    assert await _codes(state) == {}


async def test_an_integer_keyed_participation_is_never_named() -> None:
    state = _state(nullable=True, with_rate=False)
    header = state.source_schemas[0]
    header.columns[1] = SourceColumn(**{"name": "CustomerID", "type": "int", "nullable": True})
    assert await _codes(state) == {}  # nullable, but integer: zero-keyable (WP83)


# --- P2: the demo's last step --------------------------------------------------------------------

@pytest.mark.skipif(not _DEMO_STATE.is_file(), reason="the shipped demo is not checked out")
async def test_the_demo_s_order_link_is_warned_and_refused_once_the_column_is_nullable() -> None:
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
    link = by_name["link_sales_order"]
    rate = next(ref for ref in link.hub_refs if ref.hub == "hub_currency_rate")
    assert rate.key_translation is not None
    assert rate.key_translation.natural_key_columns == RATE_NORMALISED
    report = (await ValidatorAgent().run(state)).validation_report
    warned = [i for i in report.issues if i.code == WARNING and i.construct == "link_sales_order"]
    assert len(warned) == 1 and "hub_currency_rate" in (warned[0].remedy or ""), [
        (i.code, i.construct) for i in report.issues if "OPTIONAL" in i.code
    ]
    assert "link_sales_order_currency_rate" in (warned[0].remedy or "")
    header = next(t for t in state.source_schemas if t.table == "SalesOrderHeader")
    header.columns = [
        SourceColumn(**{**c.model_dump(), "nullable": True}) if c.name == "CurrencyRateID" else c
        for c in header.columns
    ]
    report = (await ValidatorAgent().run(state)).validation_report
    refused = [i for i in report.issues if i.code == ERROR and i.construct == "link_sales_order"]
    assert len(refused) == 1
