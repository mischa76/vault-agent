# ADR-0012: Attribute overlap across satellites of one parent

**Status:** Proposed
**Date:** 2026-07-30
**Decision makers:** Mischa Eismann

## Context

`E_SAT_ATTR_OVERLAP` is an error: an attribute must live in at most one satellite per parent.
The rule is canon — payload is *split* across satellites, never duplicated — and the gate has
been correct on every case this project authored itself.

WP30's AdventureWorks instrument (a schema, its boundaries and its documentation authored by
Microsoft rather than by us) failed validation on its two largest subject areas, `Production`
(25 tables) and `Sales` (19), and **both failures are this gate**. The modeler used its full
`MAX_MODELING_ATTEMPTS` budget on both and never converged — the signature of a gate asking for
something the input cannot give.

Replaying the stored traces through the validator at zero API cost (with the WP16
`attributes_without_cdk` backstop applied, so these are the errors that actually survived into
the run) gives exactly two shapes:

```
production — hub_product
  sat_product_cost_history        source_table=ProductCostHistory        StartDate, EndDate, StandardCost
  sat_product_list_price_history  source_table=ProductListPriceHistory   StartDate, EndDate, ListPrice
  sat_product_current_price_cost  (no source_table -> Product)           StandardCost, ListPrice
  => E_SAT_ATTR_OVERLAP on 'EndDate', 'StandardCost', 'ListPrice'

sales — hub_sales_order (source_entity=SalesOrderHeader), hub_store (source_entity=Store)
  sat_sales_order_details   (no source_table)  …, ModifiedDate
  sat_sales_order_amounts   (no source_table)  SubTotal, TaxAmt, Freight, TotalDue, ModifiedDate
  => E_SAT_ATTR_OVERLAP on 'ModifiedDate'
```

**These are not the same defect, and that is the whole decision.**

In `sales`, both satellites draw their payload from the *same* relation, and `ModifiedDate` is
in both. One column of one relation would be historised twice, in two tables, from one staging
model. That is precisely the duplication the rule forbids: the gate is **right**, the model is
wrong, and no narrowing should let it through.

In `production`, `sat_product_cost_history` and `sat_product_list_price_history` draw payload
from two *different* relations — `ProductCostHistory` and `ProductListPriceHistory`, Microsoft's
own per-entity history tables. Their `EndDate` columns are different columns of different
tables that merely share a generic name. Nothing collides: WP7 §7.1 gives each satellite its
own staging model, so each `EndDate` is projected once, from its own relation, into its own
satellite. The gate's stated rationale — "what would collide on the parent is the generated
column" — is true *within* one relation and false across two. And the shape it rejects is the
shape WP7 exists to make expressible.

One fact keeps this honest, because it argues the other way: `StandardCost` appears in both
`sat_product_current_price_cost` (from `Product`) and `sat_product_cost_history` (from
`ProductCostHistory`). Those *are* two records of the same business measure at different grain
— a real modelling smell, and a reviewer should see it. So "different relations" must not
become "say nothing".

## Decision

**`E_SAT_ATTR_OVERLAP` errors only when the overlapping satellites draw payload from the SAME
source relation. When the relations differ, it becomes a new warning
`W_SAT_ATTR_OVERLAP_CROSS_SOURCE`.**

The question "which relation does this satellite's payload come from?" is answered in exactly
one place, `rules.satellite_payload_relations(satellite, parent)`, returning the normalised
relation name(s):

| satellite | relations |
|---|---|
| declares `source_table` | that table |
| no `source_table`, hub parent, single-source | the hub's `source_entity` |
| no `source_table`, hub parent with `sources` (WP10) | **every** feed — the satellite splits across them |
| no `source_table`, link parent | the link's own staging (keyed by the link name) |

Two satellites are in the **same** namespace iff their relation sets *intersect*. That
intersection rule is what makes the composition cases fall out instead of needing their own
branches: a WP10 split satellite and a WP28 feed-bound satellite on the same hub do share the
named feed, so an overlap between them stays an **error** — correctly, because both would emit
that column on that feed's staging.

A satellite whose `source_table` happens to name its parent hub's own relation (a shape a real
modeller produced in WP9 §10.8) therefore lands in the same namespace as a satellite with no
`source_table`, and stays an error. That is the intended reading: it is the same relation,
written two ways.

Two consequences worth stating plainly rather than leaving to be discovered:

- The `sales` failure is **not** fixed by this ADR and must not be. It is a real modelling
  error, so it keeps its error, and the fix is steering plus the re-model loop — which now has
  one genuine error to resolve instead of also fighting three false ones.
- A warning is a *reported* signal, so the `StandardCost` smell reaches a human through the
  review queue rather than being silently blessed.

## Alternatives considered

**Keep it a hard error (status quo).** Rejected on measurement: it makes the canonical
per-entity-history shape unmodellable, and a false-positive error is maximally expensive — it
burns the whole re-model budget and ends the run with exit 3, where the same signal as a warning
would have surfaced for a human.

**Drop the cross-source case entirely (no warning).** Rejected: `StandardCost` in a current-value
satellite and in a history satellite is a genuine smell, and this project's convention is that a
heuristic non-match warns rather than either hard-failing or going silent
(`W_SAT_MAYBE_EFFECTIVITY`, `W_EFFSAT_DATE_ORDER_UNVERIFIED`, `W_MASAT_SHARED_GRAIN` are all the
same shape).

**Make the whole gate a warning.** Rejected: the `sales` case proves the error class is real and
is produced by a real model on a real schema. Downgrading it would let a model that historises
one column twice from one staging model through to generation.

**Compare declared source *columns* instead of relations (grounded runs only).** More precise in
principle — it could tell a genuinely shared column from two same-named ones — and rejected
because it would behave differently with and without a declared schema, i.e. the gate's severity
would depend on grounding. Gate semantics must not move with the input.

**Special-case audit columns (`ModifiedDate`, `rowguid`).** A denylist would make the `sales`
failure disappear without deciding anything, and it would hide the same duplication for any
business column. Rejected. (Whether audit columns belong in satellites at all is a separate
question, deliberately not opened here.)

## Consequences

- (+) The per-entity-history shape — two satellites on one parent, each from its own relation —
  becomes modellable. This is WP7's own feature, previously unreachable on a parent that has
  more than one such relation.
- (+) The remaining error class is narrower and therefore more trustworthy: when
  `E_SAT_ATTR_OVERLAP` fires now, one relation really is being historised twice.
- (+) Validator codes stay auditable — the gate narrows, a warning is added, nothing is deleted.
- (neutral) Validator codes go 34 → 35. The code stays the source of truth; the catalogue in
  `docs/operations/08-validation-gates.md` needs both the narrowed meaning and the new row.
- (−) The gate's severity now depends on `source_table`, a field the modeler may omit. A
  modeller who *should* have declared `source_table` and did not gets an error where the
  correct model would have got a warning. Mitigated by the existing `masat_source_table`
  steering rule and `W_MASAT_SHARED_GRAIN`, not eliminated: the model has no other way to know
  which relation feeds a satellite.
- (−) Two same-named columns from two relations are now assumed to be different attributes. If
  they genuinely are the same attribute arriving twice, the model gets a warning where it used
  to get an error. That is the deliberate trade: the reviewer sees it either way, and only one
  of the two readings is a build-breaking defect.

## Implementation sketch (for the WP that follows)

1. `rules.satellite_payload_relations(satellite, parent)` — one helper, `Any`-typed like its
   WP24/WP28 neighbours so `rules/` stays free of the state models. Parent lookup by name
   across hubs and links; an unresolvable parent keeps today's behaviour (a missing parent is
   already `E_SAT_UNKNOWN_PARENT`'s complaint, not this gate's).
2. Validator: group overlaps as today, then split each by namespace intersection — error for
   intersecting, `W_SAT_ATTR_OVERLAP_CROSS_SOURCE` for disjoint, with the message naming the
   relations so the reader can see *why* it is only a warning.
3. A WP16 steering rule for the class that stays an error (the `sales` shape): an attribute
   belongs to exactly one satellite per parent, with the audit-column trap named. `backstop=None`
   — a gate refuses, it does not repair, and choosing *which* satellite keeps a duplicated
   column is a modelling decision, not a deterministic repair. Regenerate the prompt fixture and
   update the steering ledger in the same commit (the WP20/WP28 precedent).
4. Acceptance signal, stated before running so it cannot be chosen afterwards. **Primary:**
   on `adventureworks_production`, `E_SAT_ATTR_OVERLAP` no longer fires for the two
   history satellites, and the run's validation passes. **Secondary, reported:** on
   `adventureworks_sales`, the `ModifiedDate` error is expected to *stay* a real error; whether
   the re-model loop now resolves it is a measurement of the steering rule, not of this ADR — if
   it does not, that is a finding about the loop, and the honest outcome is to record it rather
   than to weaken the gate that is right.

## References

- WP30 §7.3 Finding 2 (the measurement, with the traces quoted):
  `docs/architecture/backlog-2026-07/wp30-adventureworks-semantic-axis-spec.md`
- WP7 §7.1 (`source_table` — a satellite's own relation):
  `docs/architecture/backlog-2026-07/wp7-staging-refinements-spec.md`
- WP20 §2.5 (the normalised keying this gate already uses):
  `docs/architecture/backlog-2026-07/wp20-name-gates-spec.md`
- ADR-0011 (the precedent: narrow a gate on measured evidence rather than delete it)
- WP24 §2.2 (`rules/` as the single point three call sites ask):
  `docs/architecture/backlog-2026-07/wp24-multi-source-composition-spec.md`
- Gate catalogue: `docs/operations/08-validation-gates.md`
