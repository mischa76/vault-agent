---
type: spec
status: not-measured
updated: 2026-10-26
---

# WP95 — A role-qualified participation reads the relation's foreign-key column that resolves to its hub: the alias a human typed is derived (C29)

Status: **Approved and in progress** (2026-10-26, the owner's go to continue down the recommendation after C30) ·
Owner: Mischa Eismann · Author: Claude. Backlog C29 (`backlog-2026-10-candidates-3.md`, found by WP82). Builds on
WP41 (`role_names_column`, the pairing rule), WP73 (the refusal), WP82 (aliases as derived columns, carried as
`stage_aliases`).

## 1 What is wrong, in one paragraph

A role-qualified participation with no `source_key_column` is staged under `<ROLE>_<KEY>`
(`SALES_PERSON_BUSINESSENTITYID`), a column no relation carries, so the relation the offer or the evidence tier found
is refused by WP73 and the stage stays inferred — until a human types the alias at sign-off (WP82). Of WP82's seven
bindings, four carried such aliases; three of those four are derivable from the catalogue, which already says which
column is meant: the relation's one foreign-key column that resolves to the participation's hub
(`SalesPerson.BusinessEntityID → Employee.BusinessEntityID`, the hub keyed on `BusinessEntityID`), and where two
roles of one hub read one relation, the column each role names (`sales_person` → `SalesPersonID`) and, for the last
role left, the last column left. The fourth (`BusinessEntityContact`) has no foreign keys in the catalogue and stays
the human's. An alias the modeler invented (`StoreID` on `Store`, which has no such column) is no better than none.

## 2 The rules

1. **Where it applies.** In `bind_sources`, before WP73 judges a candidate relation (decided, override, carried,
   name-matched alike): every participation of a link staged here that is role-qualified, or whose alias the relation
   does not carry, and whose stage column the relation does not carry either.
2. **The candidates.** The relation's single-column foreign keys that resolve to the participation's hub: the hub
   binds the referenced table (`hub_binds_to_source_table`), or its canonical key column is the referenced column.
3. **The pairing, WP41's.** One such participation and one candidate: paired. Several: a role names a column
   (`role_names_column`) when the match is unique in both directions; when exactly one participation and one
   candidate are left unpaired, they pair. Anything else: nothing derived, WP73 refuses as today.
4. **The derivation is an alias.** The stage column is derived from the relation's column exactly as a ratified alias
   is (WP82's mechanism: derived column, null group, expected columns), recorded in the metadata as `role_columns`
   (not `ratified_columns`: no human typed it) and carried by the catalogue as `stage_aliases`, so the next increment's
   carried binding holds. A ratified alias for the same column wins.

## 3 Not this WP

Foreign keys in the carried catalogue (a relation that arrives through `carried_schemas` carries none; its aliases
arrive as `stage_aliases` instead). Unqualified participations beside others of the same hub (WP41 rule 3: never
paired). The fourth stage of WP82's four (`BusinessEntityContact`): a catalogue without foreign keys says nothing.

## 4 Pre-registration

- **P1** (keyless, the miniatures): `SalesPerson` with a `sales_person` role binds by rule with
  `SALES_PERSON_BUSINESSENTITYID` derived from `BusinessEntityID`; `Store` with roles `store` (the modeler's invented
  alias `StoreID`) and `sales_person` binds with both derived (`SalesPersonID` by name, `BusinessEntityID` by
  elimination); a relation without foreign keys, and one with two unnamed candidates for two roles, stay refused.
  The derived columns are in the metadata's `role_columns` and in `stage_aliases`. Red before the change.
- **P2** (keyless, the demo's last step replayed as WP94 measured it, with no sign-off binding): **4 inferred stages**
  (`stg_work_order_operation`, `stg_product_model`, `stg_product_subcategory`, `stg_business_entity_contact`; before:
  7); with those four bound: 0. Red before.
- **P3** (local PostgreSQL): the WP94 project regenerated with four bindings instead of seven: PASS=420 both builds,
  178 of 178 idempotent, every table's rows equal to WP94's build (the derived columns hash the same values the typed
  aliases did).

## 5 Guards

`tests/test_wp95_role_column_from_fk.py` (P1, P2), committed red before the change.

## 6 Addendum 2026-10-26, from the guards' first red run — P2's „before" was 5, not 7; the rule reaches one tier earlier

The replayed last step had **5** inferred stages without a sign-off binding, not 7: WP41's applier already aliases
`stg_sales_person_sales_territory` and `stg_sales_person_territory_history` from their ratified licenses (`Store`'s
`sales_person` as well — the rule derives only the invented `StoreID` there). And `Store` never reached WP73: the
evidence tier (WP90) declined it as `ambiguous` because the `store` participation names `StoreID` explicitly and
`Store` lacks it. So the rule lives in `rules/` (`role_columns_from_foreign_keys`) and the evidence tier excuses an
explicit alias the relation lacks when the rule derives that participation's column on it — the same reading WP73
gets at binding time. The pre-registered outcome stands: 4 inferred with no binding, 0 with the remaining four.
