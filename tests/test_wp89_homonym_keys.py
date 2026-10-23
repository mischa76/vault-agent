"""WP89 — homonym keys (C26). Committed before the change, failing.
The shape is the owner's Sales vault: `SalesOrderHeader` declares `CustomerID → Customer.CustomerID`
and also carries an `AccountNumber` — a financial account (`10-4020-000676`) — while `hub_customer`
is keyed on `Customer.AccountNumber` (`AW00000001`). The ratified key's translation is the right
reading; the same-named column was hashed instead and joined none of 31 465 rows."""
from __future__ import annotations

from vault_agent.link_proposal import apply_key_licenses
from vault_agent.state import DVModel, KeyLicense, SourceTable, VaultAgentState

CUSTOMER = SourceTable(table="Customer", schema="Sales",
                       columns=["CustomerID", "AccountNumber", "TerritoryID"])


def _header(*, fk_on_account: bool = False) -> SourceTable:
    fks = [{"columns": ["CustomerID"], "references_table": "Customer",
            "references_columns": ["CustomerID"], "references_schema": "Sales"}]
    if fk_on_account:
        fks.append({"columns": ["AccountNumber"], "references_table": "Customer",
                    "references_columns": ["AccountNumber"], "references_schema": "Sales"})
    return SourceTable(table="SalesOrderHeader", schema="Sales",
                       columns=["SalesOrderID", "CustomerID", "AccountNumber", "TotalDue"],
                       foreign_keys=fks)


def _delta() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_customer", "business_key": "AccountNumber", "source_entity": "Customer",
             "description": "c"},
            {"name": "hub_sales_order", "business_key": "SalesOrderID",
             "source_entity": "SalesOrderHeader", "description": "o"},
        ],
        "links": [
            {"name": "link_sales_order_customer", "description": "who ordered",
             "connected_hubs": [{"hub": "hub_sales_order"}, {"hub": "hub_customer"}]},
        ],
        "satellites": [
            {"name": "sat_sales_order_customer_details", "parent": "link_sales_order_customer",
             "attributes": ["TotalDue"], "source_table": "SalesOrderHeader", "description": "d"},
            {"name": "sat_customer_order_totals", "parent": "hub_customer",
             "attributes": ["TotalDue"], "source_table": "SalesOrderHeader", "description": "t"},
        ],
    })


def _run(header: SourceTable) -> tuple[DVModel, VaultAgentState]:
    state = VaultAgentState(source_schemas=[CUSTOMER, header])
    state.link_proposals.licenses.append(KeyLicense(
        source_table="SalesOrderHeader", source_column="CustomerID",
        references_table="Customer", references_column="CustomerID",
        references_schema="Sales", ratification_status="accepted",
    ))
    return apply_key_licenses(_delta(), DVModel(), state), state


# ── §2 rule 1: the ratified key's translation wins over a same-named column ────────────────
def test_a_link_participation_reads_the_declared_key_not_the_homonym() -> None:
    model, _ = _run(_header())
    [link] = model.links
    [ref] = [r for r in link.hub_refs if r.hub == "hub_customer"]
    assert ref.key_translation is not None
    assert ref.key_translation.referencing_column == "CustomerID"
    assert ref.key_translation.natural_key_column.upper() == "ACCOUNTNUMBER"


def test_a_link_satellite_reads_the_same_translation() -> None:
    model, _ = _run(_header())
    sat = next(s for s in model.satellites if s.name == "sat_sales_order_customer_details")
    assert "hub_customer" in sat.participation_translations


# ── §2 rule 2: a hub satellite read from the referencing relation, alike ───────────────────
def test_a_hub_satellite_reads_the_declared_key_not_the_homonym() -> None:
    model, _ = _run(_header())
    sat = next(s for s in model.satellites if s.name == "sat_customer_order_totals")
    assert sat.key_translation is not None
    assert sat.key_translation.referencing_column == "CustomerID"


def test_the_repair_says_which_column_it_did_not_read() -> None:
    _, state = _run(_header())
    assert any("AccountNumber" in f.message and "not read" in f.message for f in state.flags)


# ── §2 rule 3: a relation that declares the hub's key on that column itself is untouched ───
def test_a_declared_key_on_the_same_named_column_needs_no_translation() -> None:
    model, _ = _run(_header(fk_on_account=True))
    [link] = model.links
    [ref] = [r for r in link.hub_refs if r.hub == "hub_customer"]
    assert ref.key_translation is None and ref.source_key_column is None
