"""The WP34 §6 checker, tested against synthetic results BEFORE the paid run.

A checker nobody has seen fail is worth as little as a guard nobody has seen fail. Each
clause is exercised in both directions here, so the run's verdict is produced by code with
known behaviour rather than by code first exercised on the numbers it is judging.
"""
from typing import Any

from eval.wp34_check import (
    check,
    cross_domain_links,
    hub_origin,
    unsound_aliases,
    zero_satellite_hubs,
)


def _step(case: str, hubs: list[str], links: list[dict[str, Any]],
          sats: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "case": case,
        "review_items": 0,
        "model": {"hubs": hubs, "links": links, "satellites": sats or []},
    }


def _chain(**overrides: Any) -> dict[str, Any]:
    """A passing chain: 8 cross-domain links, no zero-satellite hub, review load down."""
    person = _step("adventureworks_person", ["hub_person"], [],
                   [{"name": "sat_person", "parent": "hub_person"}])
    sales_hubs = ["hub_person"] + [f"hub_s{i}" for i in range(8)]
    sales_links = [
        {"name": f"link_s{i}_person", "hubs": sorted([f"hub_s{i}", "hub_person"])}
        for i in range(8)
    ]
    sales_sats = [{"name": "sat_person", "parent": "hub_person"}] + [
        {"name": f"sat_s{i}", "parent": f"hub_s{i}"} for i in range(8)
    ]
    sales = _step("adventureworks_sales", sales_hubs, sales_links, sales_sats)
    metrics: dict[str, Any] = {
        "chain_steps": [person, sales],
        "review_items_total": 400,
        "validation_codes": {},
    }
    metrics.update(overrides)
    return {"metrics": metrics}


def test_a_hubs_domain_is_the_step_that_first_introduced_it() -> None:
    steps = _chain()["metrics"]["chain_steps"]

    origin = hub_origin(steps)

    # hub_person is present in BOTH steps; it belongs to the one that introduced it.
    assert origin["hub_person"] == "adventureworks_person"
    assert origin["hub_s0"] == "adventureworks_sales"


def test_a_link_inside_one_step_is_not_cross_domain() -> None:
    steps = [
        _step("a", ["hub_x", "hub_y"], [{"name": "link_x_y", "hubs": ["hub_x", "hub_y"]}]),
    ]

    assert cross_domain_links(steps) == []


def test_a_link_is_counted_once_even_though_later_steps_still_carry_it() -> None:
    """Each step's shape is the WHOLE vault, so a link appears in every later step too."""
    steps = _chain()["metrics"]["chain_steps"]
    steps.append(steps[-1] | {"case": "adventureworks_later"})

    assert len(cross_domain_links(steps)) == 8


def test_zero_satellite_hubs_are_the_ones_no_satellite_names_as_parent() -> None:
    final = {"hubs": ["hub_a", "hub_b"], "links": [],
             "satellites": [{"name": "s", "parent": "hub_a"}]}

    assert zero_satellite_hubs(final) == ["hub_b"]


def test_an_alias_naming_a_real_declared_column_is_sound() -> None:
    """PersonID is a real AdventureWorks column, read from the checked-in case assets."""
    steps = [
        _step("adventureworks_sales", ["hub_customer", "hub_person"], [
            {"name": "link_customer_person", "hubs": ["hub_customer", "hub_person"],
             "aliases": {"hub_person": "PersonID"}},
        ])
    ]

    assert unsound_aliases(steps) == []


def test_an_alias_naming_a_column_nothing_declares_is_reported() -> None:
    steps = [
        _step("adventureworks_sales", ["hub_customer", "hub_person"], [
            {"name": "link_customer_person", "hubs": ["hub_customer", "hub_person"],
             "aliases": {"hub_person": "NoSuchColumnAnywhere"}},
        ])
    ]

    problems = unsound_aliases(steps)

    assert len(problems) == 1
    assert "NoSuchColumnAnywhere" in problems[0]


# ── the conjunction ────────────────────────────────────────────────────────────────────


def test_all_four_clauses_can_hold() -> None:
    held, lines = check(_chain())

    assert held, "\n".join(lines)


def test_too_few_cross_domain_links_fails_even_when_everything_else_is_perfect() -> None:
    chain = _chain()
    sales = chain["metrics"]["chain_steps"][-1]
    sales["model"]["links"] = sales["model"]["links"][:3]

    held, lines = check(chain)

    assert not held
    assert any("FAILED" in line and "links:" in line for line in lines)


def test_a_rise_in_review_load_fails_the_run_even_with_the_links(  ) -> None:
    """The specific shape of the WP30.3 failure repeating with a new mechanism: the thing it
    was built for works, and the axis the arm comparison binds on moves the wrong way."""
    held, lines = check(_chain(review_items_total=700))

    assert not held
    assert any("FAILED" in line and "review:" in line for line in lines)


def test_a_zero_satellite_hub_regress_fails_the_run() -> None:
    chain = _chain()
    sales = chain["metrics"]["chain_steps"][-1]
    sales["model"]["hubs"] += ["hub_invented_a", "hub_invented_b", "hub_invented_c",
                               "hub_invented_d"]

    held, lines = check(chain)

    assert not held
    assert any("FAILED" in line and "invention:" in line for line in lines)


def test_the_gate_firing_fails_the_run_regardless_of_every_other_number() -> None:
    held, lines = check(_chain(validation_codes={"E_LINK_KEY_NOT_IN_SOURCE": 1}))

    assert not held
    assert any("FAILED" in line and "joins:" in line for line in lines)


def test_the_named_regression_fails_the_run_even_while_it_carries_a_satellite() -> None:
    """§6's invention clause has two halves and only the count was implemented, so both
    2026-08-12 runs were reported against a clause never computed — while the hub was present
    in both. The named half is stricter than the count on purpose: give the hub a satellite and
    the zero-satellite count goes quiet, which is exactly how it stayed invisible."""
    chain = _chain()
    sales = chain["metrics"]["chain_steps"][-1]
    sales["model"]["hubs"].append("hub_sales_representative")
    sales["model"]["satellites"].append(
        {"name": "sat_sales_representative_details", "parent": "hub_sales_representative"}
    )

    held, lines = check(chain)

    assert not held
    assert any("NAMED REGRESSION" in line and "hub_sales_representative" in line
               for line in lines)
