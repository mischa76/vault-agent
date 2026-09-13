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

## 7 Addendum 2026-09-12 — built; two findings the build forced, and the offline replay

**Built keyless the same day** (`link_proposal.py`, `state.py`, `orchestrator.py`, `cli.py`,
`validator.py`, `eval/run.py`; 946 tests, ruff, bare mypy). §5's keyless acceptance holds on the
ProductVendor miniature. Two things §2 did not foresee, both found by replaying the paid chain of
2026-09-12 (`eval/results/adventureworks_incremental/20260912T152704634091Z-*`) through the
proposer and applier at zero cost:

1. **Resolution is one rule for both paths, whatever the key-name match said.** §2 phrased
   PENDING as "the key was declined as `no_hub_for_key`". On the recorded vault
   `ProductVendor.BusinessEntityID → Vendor` is declined as `ambiguous_hub` (several hubs are
   keyed `BusinessEntityID`; none is Vendor's), and the candidate was dropped. Now
   `resolve_fk_target` tries the WP36 translation after *any* decline of the key match — the
   declaration names a TABLE, and a shared key name says nothing about it — and a participation
   is pending exactly when the referenced table is declared in this increment and no hub is
   built from it. The per-key proposer takes the same branch (`if hub is None:`), so proposer and
   applier cannot disagree about one foreign key.
2. **A hub binds the table it was built FROM, not only the table it is named after.** The
   modeler emitted `hub_purchase_order` with `source_entity: PurchaseOrderHeader`,
   `hub_sales_order` from `SalesOrderHeader`, `hub_sales_representative` from `SalesPerson`.
   Name-only binding (`construct_binds_to_source_table`) saw none of them, so the per-key applier
   skipped `PurchaseOrderHeader.EmployeeID` as "no hub was modelled", the relationship rule took
   the hubbed header for hub-less and built `link_purchase_order_header` beside the modeler's own
   `link_purchase_order_vendor`, and `SalesOrderHeader.SalesPersonID` stayed unresolved with the
   hub in the model. `rules.hub_binds_to_source_table(hub, table)` answers by name, then by
   `source_entity`, then by each WP10 feed; every hub↔table question in `link_proposal.py` asks
   it. Staging's spec↔relation binding (`bind_sources`) is unchanged: it binds by construct name
   on purpose, and that is a different question. Guard: `tests/test_wp37_hub_table_binding.py`.

**Offline replay, recorded hubs per step, provenance from the trace, every proposal ratified as
`--accept` would** (`replay_wp37.py`, scratch; numbers reproducible from the results files):

| Stage of the build | Links the applier adds over the 4 increments |
|---|---|
| WP34 + WP36 as measured on 2026-09-12 (paid) | 1 (`link_shopping_cart_item_product`) |
| + relationship rule, §2 as written | 4 |
| + finding 1 (one resolution rule) | 8, one of them a duplicate of a modeler link |
| + finding 2 (provenance binding) | **10**, no duplicate, no `link_relationship_incomplete` |

The ten: `document_employee`, `purchase_order_employee`, `product_vendor` (three-way),
`purchase_order_detail`, `sales_order_address`, `sales_order_ship_method`,
`sales_representative_employee`, `country_region_currency`, `person_credit_card`,
`special_offer_product`. Through `eval/wp34_check.cross_domain_links` the recorded chain reads
7 cross-domain links and the replayed one **17** — more than arm A's 16 because the counter
counts every link whose hubs entered at different steps, not only arm A's set.

**What the replay assumes, stated so the live run can falsify it.** (a) The modeler emits the
same hubs, with the same names and `source_entity`, as on 2026-09-12 — the proposals are
computed against *those*; a run that hubs differently resolves differently. (b) Every proposal
is ratified; a reviewer declining any changes the count. (c) Nothing here was built by dbt: the
relationship links' staging (one stage per link reading the relationship table, translation
views included) is keyless-only. **Pre-registered prediction for the next paid rerun, if the
user calls one: §6's link clause met (≥ 8), 12 to 15 of arm A's 16 constructible.** The cap of
the rerun protocol is already exceeded (~$24.30 of $20); no run without the user's word.

**Observed, not fixed (out of §6 scope, recorded so nobody rediscovers it).** *Role
qualification:* `SalesOrderHeader` carries `BillToAddressID` and `ShipToAddressID`, both to
`hub_address`. The per-key applier builds the first and logs the second as "already covered by
an existing link" — a same-table second key onto the same hub is a two-role link, not coverage,
and today it is neither built nor flagged. *WP34 tier 1:* a **single** hub keyed on the
referenced column is taken without asking which table it was built from; with only one hub keyed
`BusinessEntityID` in a vault, `Vendor.BusinessEntityID` would land on it. AdventureWorks never
shows this (those hubs come in packs and the tie-break asks the table), a brownfield vault
whose `source_entity` is a business term rather than a table name would lose links if tier 1
were tightened — so it is a spec question for WP34, not a silent change here.

## 8 Addendum 2026-09-13 — dbt-built once, keyless; a link with two translations had one view

§7 (c) said nothing here was built by dbt. `demo/fk_links_postgres` builds the ProductVendor
miniature — three participations, Product and Vendor translated, Vendor pending until
`hub_vendor` exists — through the pipeline's own functions and `dbt build --full-refresh` on
local PostgreSQL 16. The first build found that `StagingSpec` held ONE translation slot: the
Vendor translation overwrote the Product one, `stg_product_vendor` read
`stg_product_vendor_via_vendor` and hashed `PRODUCTNUMBER` from a view that never projected it
(`tests/test_wp37_relationship.py` had asserted that *a* `_via_` model exists, not that both
keys arrive). A stage now carries `translations: list[KeyTranslation]`, rendered as one view
with one LEFT JOIN per translation, named `stg_product_vendor_via_product_and_vendor`, its
`.yml` carrying `not_null` on each projected key and `relationships` on each surrogate.
Verified: `PASS=26`, all 3 link rows join all three hubs, a second build inserts 0 rows.
What this does NOT verify: the modeler's part (the delta is fixed by hand), and any run on
AdventureWorks — the offline replay's 10 links (§7) are still an offline number. The
per-key proposals of a relationship table are ratified by `--accept` and then flagged
`link_proposal_skipped` ("no hub was modelled for ProductVendor") — two advisory items that
restate what the relationship link already says; observed, left alone, noted in the demo README.

## 9 Addendum 2026-09-13 — the paid rerun: 16 of 16 links, and the conjunction fails elsewhere

§7 pre-registered "§6's link clause met (≥ 8), 12 to 15 of arm A's 16". Run
`20260913T021958659285Z` (`d39bc28`, $6.38): **16 cross-domain links** — arm A's count, above
the prediction — with 3 relationship proposals in purchasing and 7 in sales, every one of the ten
names §7 replayed present in the final model (`link_sales_order_ship_method` as
`link_sales_order_shipping_method`), 7 links carrying `translations`, which only the applier can
set. Joins sound. **§6 is still NOT MET**, on the clauses this WP does not touch: the modeler
built two hubs from `Vendor` (`hub_vendor` on `AccountNumber`, `hub_vendor_business_entity` on
`BusinessEntityID`) and two from `PurchaseOrderHeader`; `E_HUB_HK_COLLISION` exhausted the three
modelling attempts of step 4, was inherited by step 5's existing vault where no delta can repair
it, and step 5 exhausted its attempts too (adding `hub_shopping_cart`/`hub_shopping_cart_item`).
Four zero-satellite hubs, `hub_sales_representative` back, review 913. One consequence for this
WP: `link_product_vendor` bound its Vendor participation to `hub_vendor_business_entity` by
key-name match — correct by declaration, and the WP34 tier-1 question §7 raised, now seen live.
The modeler's inputs were unchanged from 2026-09-12 (the extractor fix touched only
`source_schema.yml`, which the modeler never sees); the duplicates are one repeat's variance until
a second says otherwise. Recorded defect, not fixed here: on the exhausted path the mapper never
runs, so the code generator's flags are appended per attempt and never deduplicated
(`source_binding` 182 in step 4 against 50 the day before) — the review clause measures that
before it measures the model.

## 10 Addendum 2026-09-13, evening — second repeat: 16 of 16 again, and the duplicate hub is a pattern

Run `20260913T063515062284Z` (`80cb960`, $6.81): **16 cross-domain links**, 8 with
applier-only translations, joins sound — the link clause at n=2 (16, 16). Everything else worse:
step 2 already exhausted its three attempts on `hub_employee`/`hub_employee_business_entity`,
every later step inherited that pair, step 4 added `hub_vendor`/`hub_vendor_business_entity`
again and step 5 `hub_person`/`hub_person_customer`; five collisions at the end, seven
zero-satellite hubs, review 637 (sum of 30/76/167/121/243, deduplicated), `pipeline_health` 0
on two `extension_conflict` links. **The duplicate is not variance.** The business-key
identifier offers two candidates for these tables in every run (`Vendor`: `AccountNumber` 0.95,
`BusinessEntityID` 0.75–0.88; `Employee`: `NationalIDNumber` 0.95, `BusinessEntityID` 0.82),
and the modeler hubs both in 3 of the 4 such steps observed today, alongside the same-as link it
also builds (`link_vendor_business_entity`). The consequence for this WP is unchanged and now
seen twice: `link_product_vendor` binds the surrogate-keyed hub by key-name match. Not this WP's
defect and not fixed here; the two remedies on the table — sharper re-model feedback naming the
hub to drop, or a backstop collapsing a surrogate-keyed duplicate onto the natural-key hub — are
model compensation and a spec question for the user.

## 11 Addendum 2026-09-13, night — the applier's resolution was sticky across modelling attempts

Run `20260913T153801752650Z` (`a21e2a3`, the collision remedy in the loop, $6.73): links **16**
(n=3), joins held, review 612 — the first time that clause held with the flags deduplicated —
invention failed at 3 zero-satellite hubs. Step 4 exposed a defect of this WP: attempt 1 hubbed
Vendor twice, the applier resolved ProductVendor's pending Vendor participation to
`hub_vendor_business_entity` by key-name match and wrote it onto the proposal; attempt 2
followed the remedy and dropped that hub, and the applier — the participation now "resolved" —
built `link_product_vendor` to a hub no longer in the model (`E_LINK_UNKNOWN_HUB`); attempt 3
re-created the hub to satisfy the link, the collision returned, the loop was exhausted, and
step 5 inherited the pair. Fixed in `dea6857`: `Participation.resolved_by_applier` marks a
resolution made against one attempt's merged model and the next attempt redoes it (cleared
when nothing resolves); proposer resolutions against the existing vault stay permanent; the
write-back stays because `E_LINK_TRANSLATION_UNRATIFIED` reads the participations as every
translation's provenance — a draft that kept the resolution local made that gate refuse the
correct link, which the keyless replay caught. Replayed over the run's recorded attempts 1 and
2 with the step-3 persisted model: attempt 2 now builds the link to `hub_vendor` by translation
with no `E_` code. Guard `tests/test_wp37_reresolve_guard.py`, written failing first. Not run
live since the fix.
