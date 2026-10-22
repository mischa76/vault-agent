"""WP83 — zero keys for nullable link participants (spec §3). Committed before the change, failing.
The shapes are the owner's AdventureWorks build: a customer is a person *or* a store (one link, two
roles of one hub, either column NULL), a bill of materials row may have no assembly (a role of
`hub_product`), and a satellite on that link reads its own stage."""
from __future__ import annotations

from typing import Any

import yaml

from vault_agent.agents.staging_generator import build_staging
from vault_agent.state import DVModel, SourceTable


def _cols(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"name": name, "type": type_} for name, type_ in pairs]


CUSTOMER = SourceTable(table="Customer", schema="Sales", columns=_cols(
    ("CustomerID", "int"), ("PersonID", "int"), ("StoreID", "int"),
    ("AccountNumber", "varchar(10)"),
))
BUSINESS_ENTITY = SourceTable(table="BusinessEntity", schema="Person",
                              columns=_cols(("BusinessEntityID", "int")))
PRODUCT = SourceTable(table="Product", schema="Production", columns=_cols(("ProductID", "int")))
BOM = SourceTable(table="BillOfMaterials", schema="Production", columns=_cols(
    ("ProductAssemblyID", "int"), ("ComponentID", "int"), ("StartDate", "datetime"),
    ("PerAssemblyQty", "decimal(8,2)"),
))
ORDERS = SourceTable(table="Orders", schema="Sales", columns=_cols(
    ("OrderID", "int"), ("OrderDate", "datetime"),
))


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
             "description": "c"},
            {"name": "hub_business_entity", "business_key": "BusinessEntityID",
             "source_entity": "BusinessEntity", "description": "b"},
            {"name": "hub_product", "business_key": "ProductID", "source_entity": "Product",
             "description": "p"},
            {"name": "hub_order", "business_key": "OrderID", "source_entity": "Orders",
             "description": "o"},
            {"name": "hub_order_day", "business_key": "OrderDate", "source_entity": "Orders",
             "description": "d"},
        ],
        "links": [
            {"name": "link_customer_business_entity", "description": "who the customer is",
             "connected_hubs": [
                 {"hub": "hub_customer"},
                 {"hub": "hub_business_entity", "role": "person", "source_key_column": "PersonID"},
                 {"hub": "hub_business_entity", "role": "store", "source_key_column": "StoreID"},
             ]},
            {"name": "link_product_assembly_component", "description": "bill of materials",
             "connected_hubs": [
                 {"hub": "hub_product", "role": "assembly",
                  "source_key_column": "ProductAssemblyID"},
                 {"hub": "hub_product", "role": "component", "source_key_column": "ComponentID"},
             ]},
            {"name": "link_order_order_day", "description": "order placed on a day",
             "connected_hubs": [{"hub": "hub_order"}, {"hub": "hub_order_day"}]},
        ],
        "satellites": [
            {"name": "sat_product_assembly_component_details",
             "parent": "link_product_assembly_component", "attributes": ["PerAssemblyQty"],
             "source_table": "BillOfMaterials", "description": "quantities"},
        ],
    })


# `bind_sources` keys an override by the normalised construct base (WP9 §6).
OVERRIDES = {
    "CUSTOMER_BUSINESS_ENTITY": "Customer",
    "PRODUCT_ASSEMBLY_COMPONENT": "BillOfMaterials",
    "ORDER_ORDER_DAY": "Orders",
}


def _stage_yaml(sql: str) -> dict[str, Any]:
    block = sql.split("{%- set yaml_metadata -%}")[1].split("{%- endset -%}")[0]
    loaded: dict[str, Any] = yaml.safe_load(block)
    return loaded


def _build(tables: list[SourceTable] | None = None, overrides: dict[str, str] | None = None) -> Any:
    tables = tables if tables is not None else [CUSTOMER, BUSINESS_ENTITY, PRODUCT, BOM, ORDERS]
    return build_staging(_model(), tables, source_overrides=OVERRIDES if overrides is None
                         else overrides, target_platform="postgres")


# ── §2 rule 1: the link's own stage ────────────────────────────────────────────────────────
def test_a_link_over_typed_integer_keys_declares_its_participants_optional() -> None:
    result = _build()
    assert result.metadata["stg_customer_business_entity"]["source_binding"] == "declared"
    sql = result.models["stg_customer_business_entity"]
    meta = _stage_yaml(sql)
    assert meta["null_columns"] == {
        "optional": ["CUSTOMERID", "PERSON_BUSINESSENTITYID", "STORE_BUSINESSENTITYID"]
    }
    assert "null_columns=metadata_dict['null_columns']" in sql
    stored = result.metadata["stg_customer_business_entity"]
    assert stored["null_columns"] == meta["null_columns"]


def test_roles_of_one_hub_list_their_role_columns() -> None:
    meta = _stage_yaml(_build().models["stg_product_assembly_component"])
    assert meta["null_columns"] == {
        "optional": ["ASSEMBLY_PRODUCTID", "COMPONENT_PRODUCTID"]
    }


# ── §2 rule 1: a link satellite's dedicated stage hashes the same value ────────────────────
def test_a_link_satellites_own_stage_declares_the_same_columns() -> None:
    result = _build()
    link_meta = _stage_yaml(result.models["stg_product_assembly_component"])
    sat_stage = next(name for name in result.models
                     if name.startswith("stg_product_assembly_component_details"))
    sat_meta = _stage_yaml(result.models[sat_stage])
    assert sat_meta["null_columns"] == link_meta["null_columns"]


# ── §2 rule 2: only where the replacement is type-safe ─────────────────────────────────────
def test_a_datetime_participant_is_left_alone() -> None:
    meta = _stage_yaml(_build().models["stg_order_order_day"])
    assert meta["null_columns"] == {"optional": ["ORDERID"]}


def test_an_untyped_relation_gets_no_null_columns() -> None:
    untyped = SourceTable(table="Customer", schema="Sales",
                          columns=["CustomerID", "PersonID", "StoreID"])
    result = _build([untyped, BUSINESS_ENTITY, PRODUCT, BOM, ORDERS])
    sql = result.models["stg_customer_business_entity"]
    assert "null_columns" not in _stage_yaml(sql)
    assert "null_columns=none" in sql or "null_columns=" not in sql


def test_an_inferred_stage_gets_no_null_columns() -> None:
    result = _build(overrides={})
    stored = result.metadata["stg_customer_business_entity"]
    assert stored["source_binding"] == "inferred"
    assert "null_columns" not in stored


# ── §2 rule 4: a stage with nothing to replace is unchanged ────────────────────────────────
def test_hub_stages_carry_no_null_columns() -> None:
    result = _build()
    for name in ("stg_customer", "stg_product", "stg_business_entity"):
        assert "null_columns" not in result.models[name], name
        assert "null_columns" not in result.metadata[name], name
