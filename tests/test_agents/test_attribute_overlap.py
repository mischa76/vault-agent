"""WP31 / ADR-0012: E_SAT_ATTR_OVERLAP narrowed to one payload namespace.

Keyless. Two satellites of one parent that repeat an attribute label are an ERROR only when
they draw payload from the SAME source relation; fed by different relations, the same-named
columns are different columns of different tables and nothing collides, so it warns.

The two shapes come from a live measurement, not from imagination: AdventureWorks `Production`
(false positive — Microsoft's per-entity history tables) and `Sales` (true positive — one audit
column duplicated across two satellites of one relation). Both are pinned at the bottom of this
file so the measurement itself cannot regress.
"""
import pytest

from vault_agent.rules.dv2_rules import DV_MODELING_RULES, satellite_payload_relations
from vault_agent.state import DVModel, Hub, HubSource, Link, Satellite, VaultAgentState

from vault_agent.agents.validator import ValidatorAgent  # isort: skip

ERROR = "E_SAT_ATTR_OVERLAP"
WARN = "W_SAT_ATTR_OVERLAP_CROSS_SOURCE"


def _hub(name: str = "hub_product", **kwargs: object) -> Hub:
    return Hub(
        name=name, business_key="product number", source_entity="Product",
        description="A product.", **kwargs,  # type: ignore[arg-type]
    )


def _sat(name: str, parent: str = "hub_product", **kwargs: object) -> Satellite:
    return Satellite(
        name=name, parent=parent, attributes=["EndDate"], description="Payload.",
        **kwargs,  # type: ignore[arg-type]
    )


async def _issues(model: DVModel) -> dict[str, list[str]]:
    report = (await ValidatorAgent().run(VaultAgentState(dv_model=model))).validation_report
    out: dict[str, list[str]] = {}
    for issue in report.issues:
        out.setdefault(issue.code, []).append(issue.message)
    return out


# --- The two measured shapes ---------------------------------------------------------------


async def test_different_source_tables_warn_and_name_the_relations() -> None:
    """§3.1 — the Production shape: two history relations under one hub."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[
            _sat("sat_product_cost_history", source_table="ProductCostHistory"),
            _sat("sat_product_list_price_history", source_table="ProductListPriceHistory"),
        ],
    )
    issues = await _issues(model)

    assert ERROR not in issues
    (message,) = issues[WARN]
    assert "PRODUCTCOSTHISTORY" in message and "PRODUCTLISTPRICEHISTORY" in message
    # a warning must not block generation — this is the whole point of the narrowing
    report = (await ValidatorAgent().run(VaultAgentState(dv_model=model))).validation_report
    assert report.passed is True


async def test_same_relation_stays_an_error_with_the_pre_wp31_message() -> None:
    """§3.2 — the Sales shape: one relation, one column, two satellites. Regression guard on
    the exact wording, because narrowing must not disturb the case the gate is right about."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[_sat("sat_product_details"), _sat("sat_product_amounts")],
    )
    issues = await _issues(model)

    assert WARN not in issues
    assert issues[ERROR] == [
        "attribute 'EndDate' appears in multiple satellites of 'hub_product': "
        "sat_product_amounts, sat_product_details"
    ]


# --- The namespace rule ---------------------------------------------------------------------


async def test_source_table_naming_the_parents_own_relation_is_the_same_namespace() -> None:
    """§3.3 — one relation written two ways (a real modeller did this, WP9 §10.8)."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[
            _sat("sat_product_details"),                      # implicit: Product
            _sat("sat_product_more", source_table="Product"),  # explicit: the same relation
        ],
    )
    assert ERROR in await _issues(model)


async def test_split_and_feed_bound_satellites_intersect_on_that_feed() -> None:
    """§3.4 — a WP10 split satellite spans every feed, so it shares the WP28-bound one."""
    hub = _hub(sources=[
        HubSource(source_table="Product", business_key_column="ProductNumber"),
        HubSource(source_table="crm_product", business_key_column="prod_no"),
    ])
    model = DVModel(
        hubs=[hub],
        satellites=[
            _sat("sat_product_details"),                          # splits across both feeds
            _sat("sat_product_crm", source_table="crm_product"),  # bound to one feed
        ],
    )
    assert ERROR in await _issues(model)


async def test_two_satellites_bound_to_different_feeds_only_warn() -> None:
    """§3.5 — one satellite per source is the canonical shape (ADR-0011)."""
    hub = _hub(sources=[
        HubSource(source_table="Product", business_key_column="ProductNumber"),
        HubSource(source_table="crm_product", business_key_column="prod_no"),
    ])
    model = DVModel(
        hubs=[hub],
        satellites=[
            _sat("sat_product_core", source_table="Product"),
            _sat("sat_product_crm", source_table="crm_product"),
        ],
    )
    issues = await _issues(model)
    assert ERROR not in issues and WARN in issues


async def test_unknown_parent_never_lowers_the_severity() -> None:
    """§3.6 — an unresolvable relation is 'unknown', not 'shares nothing'."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[
            _sat("sat_ghost_one", parent="hub_missing"),
            _sat("sat_ghost_two", parent="hub_missing"),
        ],
    )
    assert ERROR in await _issues(model)


async def test_satellites_on_a_link_parent_share_the_links_staging() -> None:
    """§3.7 — a link's staging has no source table; both satellites read the same one."""
    model = DVModel(
        hubs=[_hub(), _hub("hub_vendor")],
        links=[Link(name="link_product_vendor", connected_hubs=["hub_product", "hub_vendor"],
                    description="Supply.")],
        satellites=[
            _sat("sat_product_vendor_details", parent="link_product_vendor"),
            _sat("sat_product_vendor_terms", parent="link_product_vendor"),
        ],
    )
    assert ERROR in await _issues(model)


async def test_effectivity_satellite_ignores_source_table() -> None:
    """§3.8 — an eff-sat stages with its parent link (WP7), so source_table cannot move it
    into a namespace of its own."""
    model = DVModel(
        hubs=[_hub(), _hub("hub_vendor")],
        links=[Link(name="link_product_vendor", connected_hubs=["hub_product", "hub_vendor"],
                    driving_key=["hub_product"], description="Supply.")],
        satellites=[
            Satellite(name="sat_product_vendor_eff", parent="link_product_vendor",
                      sat_type="effectivity", attributes=["StartDate", "EndDate"],
                      source_table="SomeOtherRelation", description="Active period."),
            _sat("sat_product_vendor_terms", parent="link_product_vendor"),
        ],
    )
    assert ERROR in await _issues(model)


# --- The helper itself ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source_table", "sat_type", "parent", "expected"),
    [
        ("ProductCostHistory", None, "hub", {"PRODUCTCOSTHISTORY"}),            # declared
        (None, None, "hub", {"PRODUCT"}),                                       # hub's own
        (None, None, "multi", {"PRODUCT", "CRM_PRODUCT"}),                      # WP10 split
        ("crm_product", None, "multi", {"CRM_PRODUCT"}),                        # WP28 bound
        (None, None, "link", {"link:LINK_PRODUCT_VENDOR"}),                     # link marker
        ("SomeOtherRelation", "effectivity", "link", {"link:LINK_PRODUCT_VENDOR"}),  # ignored
        ("ProductCostHistory", None, None, {"PRODUCTCOSTHISTORY"}),  # declared, no parent
        (None, None, None, set()),                       # unknown -> empty, never "disjoint"
    ],
)
def test_payload_relations_per_adr_0012_table(
    source_table: str | None, sat_type: str | None, parent: str | None, expected: set[str]
) -> None:
    parents = {
        "hub": _hub(),
        "multi": _hub(sources=[
            HubSource(source_table="Product", business_key_column="ProductNumber"),
            HubSource(source_table="crm_product", business_key_column="prod_no"),
        ]),
        "link": Link(name="link_product_vendor",
                     connected_hubs=["hub_product", "hub_vendor"], description="Supply."),
        None: None,
    }
    sat = Satellite(
        name="sat_x", parent="p", attributes=["EndDate"], description="d",
        source_table=source_table, sat_type=sat_type or "standard",
    )
    assert satellite_payload_relations(sat, parents[parent]) == frozenset(expected)


# --- Steering (§2.3) ------------------------------------------------------------------------


def test_steering_rule_exists_and_deliberately_has_no_backstop() -> None:
    rule = next(r for r in DV_MODELING_RULES if r.id == "attribute_one_satellite")
    # A gate refuses; it does not repair. Choosing WHICH satellite keeps a duplicated column
    # is a modelling decision, so there is deliberately nothing to back it up with.
    assert rule.backstop is None
    assert "ADR-0012" in rule.origin


def test_steering_ledger_carries_the_rule() -> None:
    from pathlib import Path

    ledger = Path(__file__).parents[2] / "docs" / "architecture" / "steering-ledger.md"
    assert "`attribute_one_satellite`" in ledger.read_text(encoding="utf-8")


# --- The measurement, pinned (§3.11) --------------------------------------------------------


async def test_the_adventureworks_production_shape_only_warns() -> None:
    """The exact satellites from the 2026-07-29 `production` trace. This model FAILED
    validation before ADR-0012 and must now pass: three overlaps, all cross-source."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[
            Satellite(name="sat_product_current_price_cost", parent="hub_product",
                      attributes=["StandardCost", "ListPrice"], description="Current."),
            Satellite(name="sat_product_cost_history", parent="hub_product",
                      source_table="ProductCostHistory",
                      attributes=["StartDate", "EndDate", "StandardCost"],
                      description="Cost history."),
            Satellite(name="sat_product_list_price_history", parent="hub_product",
                      source_table="ProductListPriceHistory",
                      attributes=["StartDate", "EndDate", "ListPrice"],
                      description="Price history."),
        ],
    )
    report = (await ValidatorAgent().run(VaultAgentState(dv_model=model))).validation_report

    assert [i.code for i in report.issues if i.severity == "error"] == []
    assert report.passed is True
    # StartDate, EndDate, StandardCost, ListPrice — all four now reported, none blocking
    assert len([i for i in report.issues if i.code == WARN]) == 4


async def test_the_adventureworks_sales_shape_still_fails() -> None:
    """The exact satellites from the 2026-07-29 `sales` trace: ModifiedDate duplicated across
    two satellites of ONE relation. ADR-0012 must NOT let this through."""
    model = DVModel(
        hubs=[Hub(name="hub_sales_order", business_key="sales order number",
                  source_entity="SalesOrderHeader", description="An order.")],
        satellites=[
            Satellite(name="sat_sales_order_details", parent="hub_sales_order",
                      attributes=["OrderDate", "Status", "ModifiedDate"],
                      description="Order details."),
            Satellite(name="sat_sales_order_amounts", parent="hub_sales_order",
                      attributes=["SubTotal", "TaxAmt", "TotalDue", "ModifiedDate"],
                      description="Order amounts."),
        ],
    )
    report = (await ValidatorAgent().run(VaultAgentState(dv_model=model))).validation_report

    errors = [i for i in report.issues if i.code == ERROR]
    assert len(errors) == 1 and "ModifiedDate" in errors[0].message
    assert report.passed is False
