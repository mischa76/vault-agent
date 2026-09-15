---
type: spec
status: not-measured
updated: 2026-09-15
---

# WP40 — Key licenses: a ratified foreign key repairs the staging of what the modeler built

Status: **Approved and in progress** (2026-09-15, user: „ok, gehen wir es an und machen weiter") ·
Owner: Mischa Eismann · Author: Claude. Depends on WP34 (proposer, checkpoint), WP36/ADR-0013
(translation), WP37 (pending resolution after the modeler, `resolved_by_applier`), WP38/WP39
(satellite translation), and the widened `E_SAT_KEY_NOT_IN_SOURCE` of 2026-09-15.

## 1 Problem, measured

On the chain `20260914T213855724138Z`, which held WP34 §6, nine satellites and several links were
staged from declared relations that lack a participation's key; the widened gate now refuses the
satellites, and nothing refuses the links. Eight satellites are one declared foreign key away from
the key — `ProductCostHistory.ProductID → Product`, `hub_product` on `ProductNumber` — and **7 of
the 8 have no proposal that could license a translation**: `Product` is declared in the same
increment, `hub_product` is built by the same modeler call, so at proposal time the key is a
`no_hub_for_key` skip. Only `ShoppingCartItem.ProductID` has a ratified translated proposal, and the
modeler's own link of the same grain made the applier skip it as "covered".

Reach, replayed on the persisted step models of that chain (new modeler links per step):

| | production | sales |
|---|---|---|
| new modeler links | 17 | 24 |
| staged from no declared relation (inferred `raw_*`) | 10 | 21 |
| from a declared relation lacking a key — repairable by one declared key | 4 | 1 |
| from a declared relation lacking a key — no declared path | 3 | 0 |

and 5 of the 8 one-hop satellites (3 need a composite key).

## 2 The rule — license, then repair; never build

**Proposal.** For a declared single-column foreign key `S.c → R.x` of the increment whose
resolution against the existing vault declines, and whose referenced table `R` is declared in this
increment (so its hub, if any, comes from this modeler call): a **key license** `S.c`, category
`declared_fk_pending`. One decision per key at the link checkpoint, with the existing key syntax
(`--link "S.c"` / `--no-link "S.c"`, `--accept`). This extends ADR-0013's trigger — "a hub bound to
`R` exists" — to a hub built in the same run; everything else in the ADR holds: deterministic
trigger, visible join, typed review item.

**Resolution.** After the modeler, on every attempt, against the merged model, through
`resolve_fk_target` (WP34, WP36, WP39 — one rule): the license resolves to a hub and either a
translation, an alias (renamed key) or nothing (same name). Marked `resolved_by_applier` and redone
on the next attempt (WP37's sticky-participation lesson).

**Repair — only constructs the modeler built, and never a new one.** A resolved license, and
likewise a ratified WP34/WP36 translated or renamed link proposal, repairs what reads `S`:

1. a link whose staging binds `S` by construct name, on an unqualified participation of the
   resolved hub that carries neither alias nor translation and whose key `S` does not declare:
   `LinkHubRef.key_translation` or `source_key_column` is set;
2. a satellite on that hub with `source_table: S`: `Satellite.key_translation` (translation only —
   satellites have no alias mechanism);
3. a satellite on a link with a participation of that hub, `source_table: S`: the new
   `Satellite.participation_translations[hub]` (translation only).

Intra-increment relationships stay the modeler's (WP37 §2): a license adds no link and no hub.

**Gates follow the provenance.** `E_LINK_TRANSLATION_UNRATIFIED` and `E_SAT_TRANSLATION_UNRATIFIED`
accept translations a resolved license produced; `E_SAT_KEY_NOT_IN_SOURCE` checks a translated
participation's referencing column instead of the hub key. Flags: `link_translation` per repaired
link participation, `sat_translation` per repaired satellite, as before.

## 3 Guards before the change

`tests/test_wp40_key_license_guard.py`, committed first: (1) `ProductCostHistory.ProductID` into a
table of the same increment is a `no_hub_for_key` skip — flipped; (2) a hub-parent satellite from
that table is refused by `E_SAT_KEY_NOT_IN_SOURCE` — flipped; (3) a link from a relation lacking a
participation key, and a satellite on it, stage demanding that key — flipped; (4) a license never
creates a link — never flipped; (5) a composite key stays a skip — never flipped.

## 4 Acceptance

Keyless: the flips; renamed and same-name resolutions; no repair on a role-qualified or already
aliased participation; unratified licenses repair nothing; the gates hold for repaired constructs
and refuse a translation no license produced; the cross-vault case (a ratified translated proposal
repairs the modeler's link of the same grain instead of being skipped). Replay, zero cost, the
production and sales steps of `20260914T213855724138Z` before and after. Postgres: the demo gains a
history table with a surrogate foreign key into a table of the same increment, a satellite on the
natural-key hub, and a link from a relation lacking a key; `dbt build` green. Live: the user's call,
pre-registered after the replay.

## 5 Not in this WP

Links staged from no declared relation (the modeler's `raw_*` inferences — 31 of 41 new links above,
a binding question); a link bound by name to the wrong relation (`link_product_subcategory` reads
`ProductSubcategory` while its key lives in `Product`); composite keys; aliases for satellites;
widening `E_LINK_KEY_NOT_IN_SOURCE` to untranslated participations.

## 6 Addendum 2026-09-15 — built, replayed, on Postgres

Opening `3a9696e` (spec, kick-off, guard), feature `1f60a85`, demo `1f2adc4`. 1006 passed, ruff, bare
mypy. Three guard pins flipped, two counter-cases untouched; three existing tests updated on purpose
(the WP37 guard's Vendor skip is a license now; licenses list after relationship proposals; the
proposer telemetry dict gains `licenses` and `licenses_resolved`).

**Replay, last attempt of `20260914T213855724138Z`, before → after** (`replay_step_full.py`):

| | production | sales |
|---|---|---|
| key licenses | 0 → 27 | 0 → 16 |
| link stages lacking a key | 7 → 4 | 1 → 0 |
| `E_SAT_KEY_NOT_IN_SOURCE` | 5 → 1 | 3 → 2 |

What is left is what §5 excludes: four production links bound by name to a relation that does not
carry their key (`link_product_subcategory`, `link_product_model`, `link_product_photo`,
`link_bill_of_materials`), one link satellite with a participation that has no declared path, and
two sales-order-line satellites behind a composite key. Of the nine satellites the widened gate
refused on that chain: 1 repaired by WP39, 5 by WP40, 3 not repairable.

**On PostgreSQL 16:** `demo/fk_links_postgres` `dbt build --full-refresh` `PASS=73`; the modeler's
`link_product_inventory` (repaired under a ratified WP36 proposal for `ProductID` and a key license
for `LocationID`) loads 4 of 4 rows joining both hubs with the right pairs; its satellite 4 of 4 rows
joining the link; `sat_location_capacity_history` 3 of 3 rows joining `hub_location`; a second build
green; an orphan `LocationID` fails exactly the two location tests of the view. WP37's
relationship-table rule saw the modeler's link of the same grain and built none.

**Observed, not changed.** `apply_ratified_link_proposals` returns before its WP37 half when no
per-key proposal is ratified, so a run whose only ratified proposals are relationship tables builds
none of them. AdventureWorks never shows it (per-key proposals are always ratified alongside); a
guard and a one-line fix, recorded as a candidate.

**Pre-registered for the next paid chain, before it runs.** Licenses ≈ 27 in production and ≈ 16 in
sales (the replay's counts); `hub_sales_representative` absent; cross-domain links ≥ 21;
`E_SAT_KEY_NOT_IN_SOURCE` refusals in a step's first attempt limited to shapes with a composite key
or no declared path, so a production or sales gate may still fail if the modeler keeps them and the
loop cannot move them. **Review load may rise above 619:** each repair raises a
`link_translation` or `sat_translation` item, deliberately not aggregated — if the bar fails for
that reason alone, it is a finding about the bar (ADR-0013 §3 wants each join seen), not a
regression of the model.
