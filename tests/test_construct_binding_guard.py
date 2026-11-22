"""What construct↔relation binding must keep doing, pinned before the rule is widened (WP34).

`construct_binds_to_source_table` is the ONE rule for "does this construct name this declared
table". Three call sites depend on it — `staging_generator.bind_sources`, the validator's
link/source check, and the link proposer's near-side lookup — so a change to it moves generated
SQL, gate outcomes and applied links at once. That is worth a guard that is not about the
change being made.

The property the widening must preserve is MONOTONICITY: every pair that binds today still
binds. A widening that also *loses* a match would be a silent regression in generated staging,
and the fixtures would only catch it where a fixture happens to cover it.

The second property is that widening must not make a construct bind a DIFFERENT table. It is
safe here only because the squashed forms of the declared tables are distinct — asserted below
rather than assumed, on the real corpus, because the day a landscape declares both `SalesPerson`
and `Sales_Person` this rule becomes ambiguous and must be reconsidered rather than trusted.
"""
from __future__ import annotations

import glob
import re
from collections import defaultdict
from pathlib import Path

import pytest

from vault_agent.rules.dv2_rules import (
    construct_binds_to_source_table,
    normalize_identifier,
)
from vault_agent.source_schema import load_source_schemas

# Pairs that bind under the pre-widening rule: the base matches the table verbatim (modulo
# normalisation), or its `raw_` form does. Every one must still bind afterwards.
BINDS_TODAY = [
    ("hub_person", "Person"),
    ("hub_person", "person"),
    ("hub_customer", "CUSTOMER"),
    ("sat_customer_details", "customer_details"),
    ("link_customer_person", "customer_person"),
    ("hub_order", "raw_order"),
    ("hub_customer_address", "customer_address"),
]

# Pairs that must NEVER bind, before or after. A construct that merely PREFIXES a table name
# is a different construct: binding `hub_customer` to `CustomerAddress` would stage the wrong
# relation, which is the one defect class in this area that produced wrong data (WP24).
NEVER_BINDS = [
    ("hub_customer", "CustomerAddress"),
    ("hub_customer", "customer_address"),
    ("hub_address", "AddressType"),
    ("sat_person_details", "Person"),
    ("hub_sales", "SalesOrderHeader"),
]


@pytest.mark.parametrize(("construct", "table"), BINDS_TODAY)
def test_a_pair_that_binds_today_keeps_binding(construct: str, table: str) -> None:
    assert construct_binds_to_source_table(construct, table)


@pytest.mark.parametrize(("construct", "table"), NEVER_BINDS)
def test_a_construct_never_binds_a_table_it_merely_prefixes(construct: str, table: str) -> None:
    assert not construct_binds_to_source_table(construct, table)


def test_every_declared_table_binds_to_its_own_canonical_hub_name() -> None:
    """The test that would have caught the 2026-08-12 defect before either run was paid for.

    A hub the modeler builds for `SalesOrderHeader` is called `hub_sales_order_header` —
    `CONSTRUCT_NAME_PATTERN` allows nothing else. So every declared table must bind to that
    name, and 53 of the 68 in this corpus did not.

    Worth stating why the conservation ledger in test_link_proposal_conservation.py does NOT
    catch this: the applier flagged all five losses, so the books balanced. They balanced on a
    reason that read as legitimate — "no hub was modelled for SalesOrderHeader" — when a hub
    had been modelled and the binder could not see it. Accounting proves nothing was swallowed;
    only a claim about the real corpus proves the reasons are true."""
    unbound = []
    for schema in glob.glob("eval/datasets/*/source_schema.yml"):
        for table in load_source_schemas(Path(schema)):
            # The snake_case name CONSTRUCT_NAME_PATTERN forces: SalesOrderHeader is split at
            # the word boundaries, NOT merely lower-cased — `hub_salesorderheader` would bind
            # under the old rule too and prove nothing.
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", table.table).lower()
            canonical = "hub_" + normalize_identifier(snake).lower()
            if not construct_binds_to_source_table(canonical, table.table):
                unbound.append((canonical, table.table))

    assert not unbound, f"{len(unbound)} declared table(s) unreachable: {unbound[:5]}"


def test_the_declared_tables_stay_distinct_when_separators_are_ignored() -> None:
    """The precondition the widened rule rests on, checked against every declared schema in
    the eval corpus rather than argued. If this ever fails, `SalesPerson` and `Sales_Person`
    have become indistinguishable to the binder and the rule needs a tie-break, not a fix."""
    squashed: defaultdict[str, set[str]] = defaultdict(set)
    for schema in glob.glob("eval/datasets/*/source_schema.yml"):
        for table in load_source_schemas(Path(schema)):
            squashed[normalize_identifier(table.table).replace("_", "")].add(table.table)

    collisions = {key: names for key, names in squashed.items() if len(names) > 1}
    assert not collisions, collisions
