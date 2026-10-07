"""WP54 — a gate for the lost payload (spec §3). Committed before the change, failing. The
fixture is the eighth chain's step-3 shape: `hub_transaction` on `TransactionHistory` with no
satellite reading the table anywhere."""
from __future__ import annotations

from typing import Any

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import unread_payload
from vault_agent.state import DVModel, SourceTable, VaultAgentState

PAYLOAD = ["ReferenceOrderID", "TransactionDate", "Quantity", "ActualCost", "ModifiedDate"]


def _schema() -> list[SourceTable]:
    return [
        SourceTable(table="Product", columns=["ProductID", "Name", "ProductNumber"]),
        SourceTable(
            table="TransactionHistory",
            columns=["TransactionID", "ProductID", *PAYLOAD],
            foreign_keys=[{"columns": ["ProductID"], "references_table": "Product",
                           "references_columns": ["ProductID"]}],
        ),
    ]


def _model(extra_sats: list[dict[str, Any]] | None = None) -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_transaction", "business_key": "TransactionID",
             "source_entity": "TransactionHistory", "description": "An inventory transaction."},
        ],
        "links": [{"name": "link_transaction_product",
                   "connected_hubs": ["hub_transaction", "hub_product"],
                   "description": "The product of a transaction."}],
        "satellites": [
            {"name": "sat_product_details", "parent": "hub_product", "attributes": ["Name"],
             "source_table": "Product", "description": "Product details."},
            *(extra_sats or []),
        ],
    })


async def _issues(model: DVModel, schema: list[SourceTable] | None = None) -> list[Any]:
    state = VaultAgentState(source_schemas=schema if schema is not None else _schema(),
                            dv_model=model)
    await ValidatorAgent().run(state)
    return [i for i in state.validation_report.issues if i.code == "E_HUB_PAYLOAD_UNREAD"]


async def test_a_hub_whose_table_no_satellite_reads_is_refused_with_the_columns() -> None:
    [issue] = await _issues(_model())
    assert issue.construct == "hub_transaction"
    assert "TransactionHistory" in issue.message
    for column in PAYLOAD:
        assert column in issue.message
    assert "TransactionID" not in issue.message.split("TransactionHistory", 1)[1].split(":")[-1]
    assert issue.remedy and "hub_transaction" in issue.remedy


async def test_a_satellite_on_the_hub_or_on_its_link_reading_the_table_satisfies_it() -> None:
    on_hub = {"name": "sat_transaction_details", "parent": "hub_transaction",
              "attributes": ["Quantity", "ActualCost"], "source_table": "TransactionHistory",
              "description": "Transaction details."}
    assert await _issues(_model([on_hub])) == []
    on_link = {"name": "sat_transaction_product_details", "parent": "link_transaction_product",
               "attributes": ["Quantity"], "source_table": "TransactionHistory",
               "description": "Per transaction and product."}
    assert await _issues(_model([on_link])) == []


async def test_a_pure_association_table_has_no_payload_to_lose() -> None:
    schema = _schema()
    schema[1] = SourceTable(
        table="TransactionHistory", columns=["TransactionID", "ProductID"],
        foreign_keys=schema[1].foreign_keys,
    )
    assert await _issues(_model(), schema) == []


async def test_a_hub_of_an_undeclared_table_is_not_judged() -> None:
    assert await _issues(_model(), [_schema()[0]]) == []


def test_unread_payload_lists_the_table_columns_in_declared_order() -> None:
    model = _model()
    hub = next(h for h in model.hubs if h.name == "hub_transaction")
    assert unread_payload(hub, _schema()[1], model) == PAYLOAD
    with_sat = _model([{"name": "sat_transaction_details", "parent": "hub_transaction",
                        "attributes": ["Quantity"], "source_table": "TransactionHistory",
                        "description": "d"}])
    hub = next(h for h in with_sat.hubs if h.name == "hub_transaction")
    assert unread_payload(hub, _schema()[1], with_sat) == [
        "ReferenceOrderID", "TransactionDate", "ActualCost", "ModifiedDate"
    ]
