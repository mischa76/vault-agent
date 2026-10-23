"""WP90 — an evidence tier for link bindings (C18). Committed before the change, failing.
The shapes are the owner's Sales vault: links that several declared relations offer, which WP42
left unbound (`ambiguous`) and the owner bound by hand with seven views — five of them exactly as
this tier decides (`docs/log.md`, 2026-10-23)."""
from __future__ import annotations

from typing import Any

from vault_agent.link_proposal import component_keys, resolve_fk_target
from vault_agent.rules.dv2_rules import normalize_identifier, resolve_link_relation
from vault_agent.state import DVModel, FlagKind, SourceTable


def _fk(col: str, table: str, ref: str) -> dict[str, Any]:
    return {"columns": [col], "references_table": table, "references_columns": [ref]}


CUSTOMER = SourceTable(table="Customer", columns=["CustomerID", "AccountNumber", "TerritoryID",
                                                  "ModifiedDate"],
                       primary_key=["CustomerID"],
                       foreign_keys=[_fk("TerritoryID", "SalesTerritory", "TerritoryID")])
HEADER = SourceTable(table="SalesOrderHeader",
                     columns=["SalesOrderID", "CustomerID", "TerritoryID", "SalesPersonID",
                              "ModifiedDate"],
                     primary_key=["SalesOrderID"],
                     foreign_keys=[_fk("CustomerID", "Customer", "CustomerID"),
                                   _fk("TerritoryID", "SalesTerritory", "TerritoryID"),
                                   _fk("SalesPersonID", "SalesPerson", "BusinessEntityID")])
TERRITORY = SourceTable(table="SalesTerritory", columns=["TerritoryID", "Name"],
                        primary_key=["TerritoryID"])
SALES_PERSON = SourceTable(table="SalesPerson",
                           columns=["BusinessEntityID", "TerritoryID", "ModifiedDate"],
                           primary_key=["BusinessEntityID"],
                           foreign_keys=[_fk("TerritoryID", "SalesTerritory", "TerritoryID")])
HISTORY = SourceTable(table="SalesTerritoryHistory",
                      columns=["BusinessEntityID", "TerritoryID", "StartDate", "EndDate",
                               "ModifiedDate"],
                      primary_key=["BusinessEntityID", "StartDate", "TerritoryID"],
                      foreign_keys=[_fk("BusinessEntityID", "SalesPerson", "BusinessEntityID"),
                                    _fk("TerritoryID", "SalesTerritory", "TerritoryID")])
SCHEMAS = [CUSTOMER, HEADER, TERRITORY, SALES_PERSON, HISTORY]


def _model(*, sat_attributes: list[str] | None = None, extra: dict[str, Any] | None = None
           ) -> DVModel:
    payload: dict[str, Any] = {
        "hubs": [
            {"name": "hub_customer", "business_key": "AccountNumber", "source_entity": "Customer",
             "description": "c"},
            {"name": "hub_sales_territory", "business_key": "TerritoryID",
             "source_entity": "SalesTerritory", "description": "t"},
            {"name": "hub_sales_order", "business_key": "SalesOrderID",
             "source_entity": "SalesOrderHeader", "description": "o"},
            {"name": "hub_sales_person", "business_key": "BusinessEntityID",
             "source_entity": "SalesPerson", "description": "p"},
        ],
        "links": [
            {"name": "link_customer_region", "description": "a customer's territory",
             "connected_hubs": [{"hub": "hub_customer"}, {"hub": "hub_sales_territory"}]},
            {"name": "link_representative_region", "description": "a sales person's territory",
             "connected_hubs": [{"hub": "hub_sales_person"}, {"hub": "hub_sales_territory"}]},
        ],
        "satellites": [],
    }
    if sat_attributes is not None:
        payload["satellites"].append(
            {"name": "sat_representative_region_details", "parent": "link_representative_region",
             "attributes": sat_attributes, "description": "d"})
    for key, value in (extra or {}).items():
        payload[key].extend(value)
    return DVModel.model_validate(payload)


def _resolve(model: DVModel, link_name: str, schemas: list[SourceTable] | None = None
             ) -> tuple[str | None, str]:
    schemas = schemas if schemas is not None else SCHEMAS
    declared = {normalize_identifier(t.table): t for t in schemas}
    [link] = [lk for lk in model.links if lk.name == link_name]
    relation, grund = resolve_link_relation(
        link, model, schemas, lambda _r, fk: resolve_fk_target(model, fk, declared)[0],
        expand=lambda fk: component_keys(fk, declared),
    )
    return (relation.table if relation is not None else None), grund


# ── §2.2: the key — the relation whose primary key the participations cover ────────────────
def test_the_relation_a_hub_of_the_link_is_built_from_wins_by_its_key() -> None:
    """`Customer` beside `SalesOrderHeader`: `hub_customer` is built from `Customer`, whose
    primary key identifies its rows; the header's key is an order, no participant."""
    assert _resolve(_model(), "link_customer_region") == ("Customer", "key")


def test_without_satellites_the_sales_persons_own_relation_wins_by_its_key() -> None:
    assert _resolve(_model(), "link_representative_region") == ("SalesPerson", "key")


# ── §2.1: the payload — the relation carrying every attribute of the link's satellites ─────
def test_the_relation_carrying_the_satellites_attributes_wins() -> None:
    model = _model(sat_attributes=["StartDate", "EndDate"])
    assert _resolve(model, "link_representative_region") == ("SalesTerritoryHistory", "payload")


def test_a_generic_attribute_is_no_evidence_and_the_key_decides() -> None:
    model = _model(sat_attributes=["ModifiedDate"])
    assert _resolve(model, "link_representative_region") == ("SalesPerson", "key")


# ── §2.3: still ambiguous when the evidence does not single one out ─────────────────────────
def test_two_relations_each_a_hubs_own_stay_ambiguous() -> None:
    territory = SourceTable(table="SalesTerritory", columns=["TerritoryID", "Name", "ManagerID"],
                            primary_key=["TerritoryID"],
                            foreign_keys=[_fk("ManagerID", "SalesPerson", "BusinessEntityID")])
    schemas = [territory, SALES_PERSON]
    assert _resolve(_model(), "link_representative_region", schemas) == (None, "ambiguous")


def test_a_multi_source_feed_covers_only_its_own_key_column() -> None:
    """A hub fed by twelve relations „is built from" each; only a feed's key column counts, never
    the relation's whole primary key (WP73's lesson)."""
    dumped = _model().model_dump()
    dumped["hubs"][0]["sources"] = [  # hub_customer, multi-source
        {"source_table": "Customer", "business_key_column": "AccountNumber"},
        {"source_table": "Store", "business_key_column": "AccountNumber"},
    ]
    model = DVModel.model_validate(dumped)
    assert _resolve(model, "link_customer_region") == (None, "ambiguous")


# ── §2.4: the first two tiers are unchanged ─────────────────────────────────────────────────
def test_a_unique_offer_is_still_an_offer() -> None:
    assert _resolve(_model(), "link_customer_region", [CUSTOMER, TERRITORY]) == (
        "Customer", "offer")


# ── §2.5: every call site binds alike; staging reads the binding ────────────────────────────
def test_the_override_carries_an_evidence_binding() -> None:
    from vault_agent.link_proposal import link_source_overrides
    from vault_agent.state import VaultAgentState

    state = VaultAgentState(source_schemas=SCHEMAS, dv_model=_model())
    overrides = link_source_overrides(state)
    assert overrides["CUSTOMER_REGION"] == "Customer"
    assert overrides["REPRESENTATIVE_REGION"] == "SalesPerson"


# ── §2.6: a human sees every evidence binding, as a decision in place of the ambiguity ──────
def test_an_evidence_binding_is_a_review_decision_naming_its_rivals() -> None:
    from vault_agent.agents.orchestrator import flag_role
    from vault_agent.link_proposal import link_binding_evidence_flags
    from vault_agent.state import VaultAgentState

    state = VaultAgentState(source_schemas=SCHEMAS, dv_model=_model())
    flags = link_binding_evidence_flags(state)
    [flag] = [f for f in flags if f.asset == "link_customer_region"]
    assert flag.kind == FlagKind.LINK_BINDING_EVIDENCE and flag.reason == "key"
    assert "Customer" in flag.message and "SalesOrderHeader" in flag.message
    assert flag_role(flag) == "decision"


def test_the_mapper_raises_the_decision_and_drops_it_where_wp73_refuses() -> None:
    from vault_agent.agents.source_mapper import rebind_staging
    from vault_agent.state import VaultAgentState

    state = VaultAgentState(source_schemas=SCHEMAS, dv_model=_model())
    rebind_staging(state)
    assets = {f.asset for f in state.flags if f.kind == FlagKind.LINK_BINDING_EVIDENCE}
    assert assets == {"link_customer_region", "link_representative_region"}
    assert not [f for f in state.flags if f.kind == FlagKind.SOURCE_BINDING
                and f.asset in ("stg_customer_region", "stg_representative_region")]
    # a relation lacking a hashed column: WP73 refuses, and only its refusal is shown
    lacking = SourceTable(table="Customer", columns=["CustomerID", "TerritoryID"],
                          primary_key=["CustomerID"],
                          foreign_keys=[_fk("TerritoryID", "SalesTerritory", "TerritoryID")])
    state = VaultAgentState(source_schemas=[lacking, HEADER, TERRITORY], dv_model=_model())
    rebind_staging(state)
    kinds = {f.kind for f in state.flags if f.asset in ("link_customer_region",
                                                        "stg_customer_region")}
    assert FlagKind.BINDING_REJECTED in kinds
    assert FlagKind.LINK_BINDING_EVIDENCE not in kinds


# ── found by the pre-registered build: every call site must agree with staging's refusal ────
def test_a_pick_lacking_a_column_a_participation_names_is_declined() -> None:
    """The owner's `link_business_entity_store_sales_person` names `StoreID` (a column of
    `Customer`) for its store role while the key points at `Store`: the repair would alias against
    `Store`, staging would refuse it (WP73) — the tier declines instead."""
    model = _model(extra={"links": [
        {"name": "link_customer_rep", "description": "named column",
         "connected_hubs": [{"hub": "hub_customer"},
                            {"hub": "hub_sales_territory", "source_key_column": "RegionCode"}]},
    ]})
    assert _resolve(model, "link_customer_rep") == (None, "ambiguous")
