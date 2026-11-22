"""WP39 — two-hop translation, keyless (spec §5)."""
from __future__ import annotations

from tests.test_wp38_subtype_feed_guard import (
    _run,
    existing_vault,
    quota_history,
    sales_person,
    subtype_payload,
    subtype_state,
)
from tests.test_wp39_two_hop_guard import sales_order_header
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import propose_links
from vault_agent.state import FlagKind, Hub, SourceTable
from vault_agent.subtype_feed import subtype_feed


def _proposal_for(proposals, table):  # type: ignore[no-untyped-def]
    return [p for p in proposals.proposals if p.source_table == table]


def test_the_two_hop_proposal_names_the_middle_table_in_its_evidence() -> None:
    proposals, _ = propose_links(existing_vault(), [sales_order_header(), sales_person()])
    [p] = _proposal_for(proposals, "SalesOrderHeader")
    t = p.translation
    assert t is not None
    assert (t.referencing_column, t.through_table, t.surrogate_column, t.natural_key_column) == (
        "SalesPersonID", "Employee", "BusinessEntityID", "NATIONALIDNUMBER"
    )
    assert any("is itself a declared foreign key to Employee" in e for e in p.evidence)


def test_the_hop_also_follows_an_ambiguous_key_name() -> None:
    """The real vault: several hubs keyed BusinessEntityID, none built from SalesPerson."""
    vault = existing_vault()
    vault.hubs += [
        Hub(name="hub_person", business_key="BusinessEntityID", source_entity="Person",
            description="p"),
        Hub(name="hub_store", business_key="BusinessEntityID", source_entity="Store",
            description="s"),
    ]
    proposals, _ = propose_links(vault, [sales_order_header(), sales_person()])
    [p] = _proposal_for(proposals, "SalesOrderHeader")
    assert p.target_hub == "hub_employee"


def test_an_undeclared_middle_table_stays_a_skip() -> None:
    proposals, skipped = propose_links(existing_vault(), [sales_order_header()])
    assert _proposal_for(proposals, "SalesOrderHeader") == []
    assert "SalesOrderHeader.SalesPersonID" in [s.asset for s in skipped]


def test_two_onward_keys_on_the_middle_column_are_not_chosen_between() -> None:
    doubled = sales_person()
    doubled.foreign_keys.append(doubled.foreign_keys[0].model_copy(
        update={"references_table": "Person"}))
    proposals, _ = propose_links(existing_vault(), [sales_order_header(), doubled])
    assert _proposal_for(proposals, "SalesOrderHeader") == []


def test_the_feed_covers_tables_keyed_on_the_subtype_key_only() -> None:
    store = SourceTable(table="Store", columns=["BusinessEntityID", "Name", "SalesPersonID"],
                        foreign_keys=[{"columns": ["SalesPersonID"],
                                       "references_table": "SalesPerson",
                                       "references_columns": ["BusinessEntityID"]}])
    feed = subtype_feed(subtype_state().resolutions.proposals[0], existing_vault(),
                        [sales_person(), quota_history(), store])
    assert feed is not None
    assert [name for name, _ in feed.referencing] == ["SalesPersonQuotaHistory"]
    t = feed.translation_for("SalesPersonQuotaHistory")
    assert t is not None and (t.referencing_column, t.through_table) == (
        "BusinessEntityID", "Employee"
    )
    assert feed.translation_for("Store") is None


async def test_the_quota_history_satellite_is_translated_and_passes_both_gates() -> None:
    _, state = await _run(subtype_state(), subtype_payload("SalesPersonQuotaHistory"))
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_sales_person_details"]
    assert sat.key_translation is not None and sat.key_translation.through_table == "Employee"
    assert [f.asset for f in state.flags if f.kind == FlagKind.SAT_TRANSLATION] == [
        "sat_sales_person_details"
    ]
    report = (await ValidatorAgent().run(state)).validation_report
    assert not [i.code for i in report.issues if i.code.startswith("E_SAT_")]
    view = state.artifacts.staging_models["stg_sales_person_details_via_employee"]
    assert "ref('SalesPersonQuotaHistory')" in view and "r.NATIONALIDNUMBER" in view
