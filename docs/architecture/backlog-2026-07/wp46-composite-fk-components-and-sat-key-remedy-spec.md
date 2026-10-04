---
type: spec
status: not-measured
updated: 2026-10-04
---

# WP46 — Composite foreign keys read per component, and a remedy for a satellite whose relation lacks its parent's key

Status: **Approved and in progress** (2026-10-04, user: „ok, mach 2 und 3, leg los" on the four
alternatives to a ratified translation WP) · Owner: Mischa Eismann · Author: Claude. Touches the
link proposer (WP34, WP36, WP39, WP40/41), `E_SAT_KEY_NOT_IN_SOURCE` (2026-09-15), the repair
memory (WP44), the FK-links Postgres demo. No prompt change; no new model call; no ratification
beyond the checkpoint that already ratifies proposals and licenses.

## 1 Problem, measured

The chain `20261004T013339024833Z` (`docs/log.md` 2026-10-04, „Paid chain run") is red in two
steps on one class: a link satellite read from a relation that carries `hub_product`'s
**surrogate** `ProductID` but **declares no single-column key into `Product`** to license a
translation from. `sat_sales_order_line_detail` reads `SalesOrderDetail`, whose `ProductID` is
half of the composite key `(SpecialOfferID, ProductID) → SpecialOfferProduct`; the proposer skips
composite keys whole (`composite_key`, WP34 §3.2). `sat_work_order_operation_detail` reads
`WorkOrderRouting`, whose `ProductID` has no declared key at all — AdventureWorks declares none.
In both the gate is right: the stage would hash `PRODUCTNUMBER` from a relation that does not
have it. The other participation of each satellite was repaired (through `SalesOrderHeader`,
through `Location`); the product one could not be.

The catalogue is not silent on the first case. `SpecialOfferProduct` declares `ProductID →
Product.ProductID` and `SpecialOfferID → SpecialOffer.SpecialOfferID`, both single-column. A
composite inclusion dependency projects onto its components: every `SalesOrderDetail.ProductID`
is a `SpecialOfferProduct.ProductID`, and every one of those is a `Product.ProductID`. The same
argument WP39 makes for one key one table further, made per component.

## 2 The rule

### 2.1 A composite foreign key is read per component, one table further

For a composite key `R.(c1 … cn) → T.(r1 … rn)` with `T` declared: for each position `i`, if `T`
declares exactly one single-column key on `ri` to another table `U` (`T.ri → U.u`), the proposer
treats `R.ci → U.u` as a declared single-column key and runs the ordinary per-key path on it —
target hub, translation (WP36), licence (WP40). Components with no such onward key stay a
typed skip (`composite_key`) naming the unresolved columns; a key whose `T` is not declared
stays a skip whole, as today. The derived key carries the evidence „component `i` of the
composite key into `T`, read through `T.ri → U.u`". Downstream nothing changes: a proposal or
licence from a derived key repairs the modeler's links and satellites through the same
`apply_key_licenses` / `apply_ratified_link_proposals` as any other.

What this does **not** do: it never pairs `R.ci` with `T.ri` itself as a key into a hub built
*from* `T` — `T` is a relationship table, and pairing a component with a composite hub is the
WP45 §5 item, still open.

### 2.2 The satellite gate says what to do, and the loop remembers it

`E_SAT_KEY_NOT_IN_SOURCE` gets a deterministic remedy, `rules.satellite_key_remedy`: the parents
whose key the relation *does* carry — hubs whose `hub_key_columns` are all declared on it, links
all of whose participation columns are — named as re-parent candidates, else „drop it"; the text
is sent to the modeler beside the diagnosis (as `hub_collision_remedy` is). The issue **retires
the satellite's shape** (WP44): `RetiredConstruct` gains `parent` and `source_table`, and the
modeler's `drop_retired` drops a satellite only when name, parent and relation all match the
retirement — a re-parented satellite of the same name passes and faces the gate again. The
dropped satellite is one `retired_orphan` decision naming its payload (the human places it; the
rule does not), and one `backstop` event `retired_reemitted`.

So a satellite the modeler cannot place correctly costs the run a decision item, not a red
gate, after at most one more attempt; and a satellite it *can* place is repaired as before.

## 3 Guards before the change

Committed first, failing; then the change:

1. Proposer: a composite key whose middle table declares onward single-column keys on both
   components yields two per-key results (a translated proposal for the hub keyed on the natural
   key; a licence for the undeclared hub) and no skip; with an onward key on one component only,
   one result and one `composite_key` skip naming the other column; with the middle table
   undeclared, the skip whole, as today (the existing pins in `test_link_proposal` and
   `test_wp40_key_license_guard` keep passing).
2. End to end, keyless: the ratified derived key repairs a modeler-built link's product
   participation and its link satellite's participation from `SalesOrderDetail` with a
   translation through `Product`; the validator raises no `E_SAT_KEY_NOT_IN_SOURCE`.
3. Remedy: for `sat_work_order_operation_detail` on a link with `hub_product` read from
   `WorkOrderRouting`, the issue's remedy names `hub_work_order` as the parent whose key the
   relation carries and retires the satellite's shape (name, parent, relation).
4. Repair memory: a satellite re-emitted with the same parent and relation is dropped with one
   `retired_orphan` flag naming its payload and one backstop event; the same name on another
   parent passes.
5. The FK-links demo builds the `SalesOrderDetail` shape on PostgreSQL (§4).

## 4 Pre-registration

**Postgres (keyless).** `demo/fk_links_postgres` gains `SpecialOffer`, `SpecialOfferProduct` and
`SalesOrderDetail` (declared with the composite key and the two onward keys), a modeler link
`link_sales_order_line` (`hub_sales_order`, `hub_product`) and `sat_sales_order_line_detail`
from `SalesOrderDetail`. Predicted: the derived `ProductID → Product` key licenses a translation
on both; `dbt build --full-refresh` green from an empty schema; every line row joins its order
and its product through the view; a second build inserts nothing.

**The next live chain**, if the modeler builds the 2026-10-04 shapes again:
- **P1.** Step 5: `E_SAT_KEY_NOT_IN_SOURCE` 1 → 0 — `sat_sales_order_line_detail` repaired
  through `Product` under the derived key; the `composite_key` skip 1 → 0 (both components
  resolve). Step 5's gate green, unless a class not yet seen appears.
- **P2.** Step 3: the gate fires once in attempt 1 with the remedy naming `hub_work_order`; then
  either the modeler re-parents and the step is green on that class, or it re-emits and the
  satellite is dropped — one `retired_orphan`, one backstop fire, gate green on that class.
  Either way `validation_gate` 1.0 in step 3 unless something else fails.
- **P3.** Nothing else moves: steps 1, 2, 4 unchanged in their key repairs; WP34 §6 holds.
- **P4.** `review_decisions` rises by at most 1 (the orphan), falls by 0 — translations are
  disclosures of a repaired join, decisions of a review; the two new `sat_translation` flags
  are decisions under WP43's table, so +2 there if both fire.

## 5 Not in this WP

- Pairing a component with a hub built from the middle table (a composite-keyed
  `hub_special_offer_product`): WP45 §5.
- Inferring a key from a column name alone (`ProductID` with no declared key anywhere): refused
  on purpose; that is the ratified WP the user set aside, and `WorkOrderRouting` is its case.
- Re-parenting the orphaned payload automatically.

## 6 Results

*(appended after the change, the Postgres build, and the next live chain)*

**2026-10-05 — built keyless and on PostgreSQL.** Commits `5a9c8b5` (guards, failing) and
`cec2f9f` (the change and the demo). §2.1: `composite_components` / `component_keys`, the per-key
path lifted into `_propose_for_key`, the relation offer and resolution taking an `expand` of
composite keys through all four callers and the wrong-column gate — without the last, the
modeler's link reading the relation was not recognised as reading it and stayed unrepaired
(found by guard 2). §2.2: `satellite_key_remedy`, `RetiredConstruct.parent/source_table`,
`drop_retired` on the satellite shape. Guards 1–5 pass; pytest 1102, ruff, mypy clean. The
Postgres half of §4 held exactly: `PASS=130` from an empty schema (113 the day before), 3 of 3
line rows join order and product as seeded, 3 of 3 satellite rows join the link, second build
unchanged, no `composite_key` skip. The chain half (P1–P4) is **not yet measured live**.

**2026-10-05 — measured live** (chain `20261004T140130528908Z`, `docs/log.md` „Second paid chain
run"). **P1** held on its codes (`E_SAT_KEY_NOT_IN_SOURCE` 0 in step 5, `composite_key` skip 0) but
the modeler built no `SalesOrderDetail` satellite, so the component's translation was not
exercised live; evidence stays the Postgres build. **P2 held, re-parent branch:** the gate fired
in step 3 attempt 1, the remedy named `hub_work_order`, attempt 2 hung the satellite there; no
orphan, no backstop fire. **P3:** `validation_gate` 1.0 in all five steps — the first all-green
chain. **P4 held** (review 135 decisions, band 118–178).
