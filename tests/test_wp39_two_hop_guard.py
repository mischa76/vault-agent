"""WP39 guard, committed BEFORE the capability (spec §4).

Three pins on the SalesPerson miniature of WP38 (`hub_employee` keyed on NationalIDNumber;
`SalesPerson.BusinessEntityID → Employee`):

* ``test_a_key_into_a_hubless_subtype_is_a_skip`` — FLIPPED by WP39: the key reaches
  `hub_employee` through `Employee`, one hop further.
* ``test_a_chain_whose_middle_table_has_a_hub_is_decided_by_that_hub`` — never flipped: the
  nearest hub always wins.
* ``test_the_subtype_sentence_covers_the_subtype_table_only`` — FLIPPED by WP39: the sentence
  names the tables whose key references the subtype's key.

WP38's own pin ``test_a_table_that_references_the_subtype_is_not_translated`` is the satellite
side of the first flip and is flipped by WP39 in the same commit.
"""
from __future__ import annotations

from tests.test_wp38_subtype_feed_guard import (
    _run,
    existing_vault,
    sales_person,
    subtype_payload,
    subtype_state,
)
from vault_agent.link_proposal import propose_links
from vault_agent.state import Hub, SourceTable


def sales_order_header() -> SourceTable:
    return SourceTable(
        table="SalesOrderHeader",
        columns=["SalesOrderID", "SalesOrderNumber", "SalesPersonID"],
        foreign_keys=[{"columns": ["SalesPersonID"], "references_table": "SalesPerson",
                       "references_columns": ["BusinessEntityID"]}],
    )


def test_a_key_into_a_hubless_subtype_reaches_the_supertype_hub() -> None:
    """Flipped by WP39 in its own commit (pinned at the WP39 opening commit as: skip
    `no_hub_for_key`)."""
    proposals, skipped = propose_links(existing_vault(), [sales_order_header(), sales_person()])
    [proposal] = [p for p in proposals.proposals if p.source_table == "SalesOrderHeader"]
    assert (proposal.target_hub, proposal.category) == ("hub_employee", "declared_fk_translated")
    assert proposal.translation is not None
    assert proposal.translation.through_table == "Employee"
    assert "SalesOrderHeader.SalesPersonID" not in [s.asset for s in skipped]


def test_a_chain_whose_middle_table_has_a_hub_is_decided_by_that_hub() -> None:
    vault = existing_vault()
    vault.hubs.append(Hub(name="hub_sales_person", business_key="BusinessEntityID",
                          source_entity="SalesPerson", description="the salesperson"))
    proposals, _ = propose_links(vault, [sales_order_header(), sales_person()])
    [proposal] = [p for p in proposals.proposals if p.source_table == "SalesOrderHeader"]
    assert proposal.target_hub == "hub_sales_person" and proposal.translation is None


async def test_the_subtype_sentence_names_the_tables_keyed_on_the_subtype_key() -> None:
    """Flipped by WP39 in its own commit (pinned as: "covers `SalesPerson` itself only")."""
    prompt, _ = await _run(subtype_state(), subtype_payload())
    assert "itself only" not in prompt
    assert "`SalesPersonQuotaHistory`" in prompt
