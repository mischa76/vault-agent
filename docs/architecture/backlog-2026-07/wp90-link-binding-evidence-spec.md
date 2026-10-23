---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP90 — An evidence tier for link bindings: a link several relations offer binds to the one its satellites' payload or its participations' key singles out (C18, first half)

Status: **Approved and in progress** (2026-10-23, the owner's yes to the second to „allow the evidence-based third binding tier,
which overrides WP42's decision") · Owner: Mischa Eismann · Author: Claude. Backlog C18
(`backlog-2026-10-candidates-2.md`); the second half — a binding field for link stages at sign-off — belongs to C4
(WP82, reserved) and is not this WP.

## 1 What is wrong, in one paragraph

`rules/dv2_rules.resolve_link_relation` binds a link by name, else by the one declared relation whose offer covers
its participations; two or more fitting relations bind nothing (`ambiguous`), „deliberately no third tier" (WP42
§2): picking one would be a guess with wrong data as the failure mode. The stage then reads an inferred `raw_<base>`
that does not exist. The owner's build needed hand-made views for five such links; the paid chain of 2026-10-23
left five `ambiguous`; over all stored chain steps (`eval/results/adventureworks_incremental/*dv_model.yml`, keyed
catalogue) **129 link occurrences are ambiguous**. The catalogue holds the evidence WP42 did not use: which relation
carries the attributes of the link's satellites, and which relation's primary key the link's participations cover.

## 2 The rules (this adds the third tier WP42 §2 declined; WP42's record stays as written)

Only when **two or more** relations fit the offer (today's `ambiguous`); name and a unique offer are tried first,
unchanged.

1. **Payload.** The link's satellites (parent = the link) together name a set of attributes. A fitting relation
   qualifies when it declares **every** one of them. Exactly one qualifies → bind it, `grund = "payload"`. A generic
   attribute every relation carries (`ModifiedDate`, `rowguid`) qualifies all and decides nothing.
2. **Key.** Among the payload's qualifiers (or all fitting relations when none qualified), a relation qualifies when
   its declared primary key is non-empty and covered by the link's participations: by the columns of its foreign
   keys that resolve to a hub of the link (composite keys by component, WP46), by the key column of a multi-source
   hub's feed from this relation, or wholly when a **single-source** hub of the link is built from this relation (the
   primary key identifies that hub's rows, whatever the hub is keyed on — `Customer.CustomerID` for `hub_customer`
   keyed on `AccountNumber`). Exactly one qualifies → bind it, `grund = "key"`.
3. **Otherwise `ambiguous`**, as today.
4. **One rule, every call site.** The key repair (`apply_key_licenses`), both link gates, the WP85 grain gate and
   staging's overrides (`link_source_overrides`) all call `resolve_link_relation`; the repair's model gains the
   satellites so the payload tier sees what staging sees. `link_source_overrides` treats `payload`/`key` like `offer`.
5. **A human sees it.** Every evidence binding raises a `LINK_BINDING_EVIDENCE` flag (role `decision`, reason the
   tier) naming the chosen relation and the rivals — in place of the `ambiguous` `SOURCE_BINDING` decision it
   replaces, so the decision count does not rise. A binding the WP73 check refuses stays refused.

## 3 Acceptance (keyless)

`tests/test_wp90_link_binding_evidence.py`: key tier (a hub's own relation; foreign-key columns), payload tier, a
generic attribute deciding nothing, two own relations staying ambiguous, a multi-source feed covering only its key
column, a unique offer unchanged, the override, the flag and its role. The rest of the suite unchanged except tests
pinning an `ambiguous` binding the tier now decides — updated in the same commit, with the reason.

## 4 Pre-registration

Measured by a prototype of exactly these rules before this spec (`docs/log.md`, 2026-10-23); the implementation must
reproduce it:

- **P1** over the stored chain steps: 129 ambiguous occurrences → 0; 102 by key, 27 by payload.
- **P2** the owner's Sales run (keyed catalogue): the five links the owner bound by hand bind exactly to the tables
  the owner's views read — `PersonCreditCard`, `SalesPerson`, `SalesTerritoryHistory`, `Store`, `Customer`.
- **P3** (keyless `dbt build`, PostgreSQL) that run regenerated (WP85's remedies, WP89) and built twice into a fresh
  schema **without** those five views (only `raw_work_order_product_location` and `raw_sales_order_currency_rate`
  applied): PASS for every model; the five links' row counts equal `aw`'s (built from the hand views); second build
  idempotent.
- **P4** the paid chain's last step (`20261022T234439976097Z`): its five `ambiguous` stages bind (`Customer`, `Store`,
  `SalesPerson`, `SalesTerritoryHistory`, `PersonCreditCard`).

Not predicted: which validator issues the newly bound links raise (each listed in the log); wall time.
