---
type: spec
status: keyless-only
updated: 2026-09-12
---

# WP37 — Relationship-table links: a hub-less table with two keys is a link between their targets

Status: **Approved and in progress** (2026-09-12, user: „mach WP37") · Owner: Mischa Eismann ·
Author: Claude. Depends on WP34 (proposer, checkpoint, applier), WP36 (translation), and the
extractor fix of 2026-09-12 (90 foreign keys; without it the second key of every relationship
table is missing and this WP has nothing to work on).

## 1 Problem, measured

Arm A's 16 cross-domain links split 8 / 6 / 2: direct foreign key between two hubs' tables,
the two keys of a **relationship table** that gets no hub of its own, none. WP34's proposer
only knows the first shape — a link needs a hub on the referencing side — so on the 2026-09-12
rerun all four translated proposals from `ProductVendor`, `PurchaseOrderDetail`,
`SpecialOfferProduct`, `ShoppingCartItem` were ratified and three were dropped: no hub for the
referencing table. Correctly: those tables are m:n or detail tables. Their meaning is the link
among the tables they reference — `ProductVendor` IS `hub_vendor ↔ hub_product ↔ hub_unit_measure`
(arm A built exactly that, with the same three participations). The FK-evidence ceiling with
this rule is 15 of 16 (`docs/log.md`, 2026-09-12).

## 2 The rule — deterministic, no judgement

For a table `T` of the increment with **two or more single-column** declared foreign keys: `T`
is a *relationship-table candidate*. Each key is a **participation**: the referenced table, the
referencing column, and — resolved the way WP34/WP36 resolve one FK — the target hub with its
alias or translation. Resolution happens twice:

- **at proposal time**, against the existing vault: participations whose referenced table is
  hubbed there resolve now; those referencing a table of *this* increment stay **pending** (the
  modeler has not run). A candidate becomes a `RelationshipLinkProposal` only if **at least one**
  participation resolves now — a purely intra-increment table is the modeler's own business.
- **at apply time**, after the modeler, against the merged model: pending participations are
  resolved against the hubs the modeler just built (same helpers, translation included —
  `hub_vendor` on `ACCOUNTNUMBER` vs `ProductVendor.BusinessEntityID` is a translation).

**Apply only when complete.** If a hub bound to `T` exists, the near-hub proposals cover it and
the relationship proposal is dropped with an info log — the two shapes never both apply. If
every participation resolves to a **distinct** hub, one link `link_<base(T)>` is added to the
delta with those participations (alias / translation per ref, as WP34/36 render them). If any
participation stays unresolved, or two resolve to the same hub, **nothing is built** and a typed
flag `LINK_RELATIONSHIP_INCOMPLETE` names the participation: a link with a missing participation
has a different grain, and a wrong grain in a link over history is bad data, not a bad guess.

## 3 Ratification, HITL, staging

- One proposal per table, one decision: key `Table.*` (`--link "ProductVendor.*"`), `--accept`
  ratifies it like the others. Rendered as its own line: *ProductVendor: relationship table →
  link hub_product · hub_unit_measure · (Vendor, pending) — applies only if ProductVendor gets no
  hub of its own*. Per-FK proposals for the same table stay (they are needed if `T` IS hubbed).
- Staging: `link_source_overrides` binds `link_<base(T)>` to `T` (existing mechanism, keyed by
  the link base), so the link's stage reads the relationship table and hashes every
  participation's key from it, translation models included (WP36).
- Recorded in `eval/run.py` as category `relationship_table` beside the per-FK categories.

## 4 Guards before the change

All byte-identity fixtures; `tests/test_wp37_relationship_guard.py` pins that the WP34 and WP36
miniatures (one FK each) yield no relationship proposal, and pins today's behaviour for a two-key
hub-less table (per-FK proposals only, nothing built) — the second pin is flipped by this WP.

## 5 Acceptance

Keyless: the two-key miniature yields one relationship proposal with one resolved and one
pending participation; ratified, the applier resolves the pending one against the delta and
builds a three-way or two-way link with alias/translation per ref; a hubbed `T` yields no
relationship link; an unresolvable participation yields the flag and no link; staging binds the
link to `T`; the gates hold; every fixture untouched.

Live, later and only on the user's word: the WP30 rerun with the full keys and both rules —
pre-registered prediction **up to 15 cross-domain links**, likely fewer because the modeler
must hub what the pending participations need; §6's link clause (8) met.

## 6 Not in this WP

Composite keys; a relationship table with **one** resolvable key (stays a skip); tables the
modeler hubs (near-hub path); role-qualification when two keys hit the same hub (flagged, not
guessed); any change to the modeler.
