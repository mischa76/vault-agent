---
type: spec
status: keyless-only
updated: 2026-09-12
---

# WP36 — Surrogate→natural-key translation for FK-derived links

Status: **Approved and in progress** (2026-09-12; ADR-0013 accepted the same day) · Owner: Mischa
Eismann · Author: Claude. Depends on: WP34 (the proposer and the ratification checkpoint), WP24
(canonical staging keys through `rules/`), ADR-0009/ADR-0011 (the staging patterns this composes
with). Closes the design question the 2026-08-12 audit isolated; the WP30 arm-B rerun (its
protocol, step 0) measures the full mechanism **after** this WP.

## 1 Problem, in the four cases that exist

AdventureWorks declares referential integrity on **surrogates**; the vault keys its hubs on the
**natural business key**, as DV2.0 asks and as the source's own column comments endorse
(`ProductID` — "Primary key for Product records"; `ProductNumber` — "Unique product
identification number"). Read from the schemas and the recorded run of 2026-08-12:

| increment | referencing table.column | references | hub | keyed on | today |
|---|---|---|---|---|---|
| purchasing | `Purchasing.ProductVendor.ProductID` | `Production.Product.ProductID` | `hub_product` | `PRODUCTNUMBER` | skip `no_hub_for_key` |
| purchasing | `Purchasing.PurchaseOrderDetail.ProductID` | same | same | same | skip |
| sales | `Sales.SpecialOfferProduct.ProductID` | same | same | same | skip |
| sales | `Sales.ShoppingCartItem.ProductID` | same | same | same | skip |

An FK-derived proposer that matches on the hub's key column can never bridge this, and it is not
an alias: `ProductNumber` is not in the referencing table at all. Bridging is a **join through
the referenced relation**: `ShoppingCartItem ⋈ Product on ProductID`, projecting `ProductNumber`.

## 2 Trigger — deterministic, no judgement (ADR-0013 §1)

For a single-column declared FK `T.X → R.Xref`, after today's match on the key column finds no
hub:

1. exactly **one** existing hub binds to `R` by name (`construct_binds_to_source_table(hub.name,
   R)`; `hub_product` binds `Product`, `hub_product_category` does not — the prefix guard of
   `4e8d1d1` is what makes this exact);
2. that hub's canonical key column `Y` (`canonical_hub_key_column`) differs from `Xref` under
   `normalize_identifier`;
3. if `R` is declared in this increment's schema, it must declare both `Xref` and `Y`; if `R` is
   not declared here (the normal incremental case — `Product` came in a prior step), the hub's
   own provenance stands for `Y ∈ R`: the hub was modelled from `R` on `Y`.

Then the FK becomes a proposal of category **`declared_fk_translated`** carrying a typed
`KeyTranslation(through_table=R, through_schema, surrogate_column=Xref, natural_key_column=Y)`.
Condition 3's failure is a new typed skip reason, `translation_key_missing`. Everything else —
composite keys, ambiguity, no hub at all — skips exactly as today. **Counter-case, pinned by
test:** a hub keyed on the surrogate itself never triggers this; the FK is an ordinary
`declared_fk_same_name` proposal and the capability is a no-op, not a wrong join.

## 3 Mechanism — the translation is visible dbt code (ADR-0013 §2)

A ratified translated proposal produces, through `apply_ratified_link_proposals`, a link whose
target participation carries `LinkHubRef.key_translation` (typed, beside `source_key_column`,
which stays `None` for it). The staging pass then emits **two** models for that link:

- `stg_<link>_via_<r>` — a plain view, the **translation model**: the referencing relation
  left-joined to `R` on `T.X = R.Xref`, projecting every column of `T` plus `R.Y` under the
  hub's canonical name. Relations are referenced the way the rest of the staging layer
  references them (`source()` when bound to a block, the bare relation otherwise), taken from
  the specs the binder already produced — `R`'s binding is the one its hub's staging uses, so
  the two cannot disagree.
- the link's ordinary AutomateDV `stage` model, whose `source_model` is the translation model
  instead of `T`. Its hashed columns are unchanged: the FK hash is taken over the canonical `Y`,
  exactly as for every other participation (WP24), because `Y` now exists in the source it reads.

Unmatched surrogates and duplicate matches are **data-time** facts no model-time gate can see.
The translation model therefore ships its own `schema.yml` with a `not_null` test on the
projected `Y` (an unmatched surrogate fails `dbt build`, loudly — the gate refuses at build
time) and a `relationships` test from `T.X` to `R.Xref`. Nothing is repaired silently: the
join is a LEFT JOIN so the row count of `T` is preserved and the failure is attributable to the
row, not swallowed by an inner join.

## 4 HITL and gates — typed, never message text (ADR-0013 §3)

- The checkpoint renders a translated proposal as its own review class: `→ link to hub_product
  (declared_fk_translated: ProductID → ProductNumber through Production.Product)`.
- A new `FlagKind.LINK_TRANSLATION` flag per applied translation says *this link required
  surrogate translation through R* in the review queue and the report.
- `E_LINK_KEY_NOT_IN_SOURCE` gains a translation branch: the referencing column `X` must be
  declared on `T`, and when `R` is declared, `Xref` and `Y` on `R`. It stays an error, for the
  reason the WP34 gate is one.
- `eval/wp34_check.py`'s soundness clause (`unsound_aliases`) learns the shape: a translated
  participation has no alias and is checked on `X ∈ T` instead.
- Metadata: `automatedv.yml`'s staging block records the translation per link, so a reader of
  the artifacts sees the join without reading SQL.

## 5 Guards before the change

- All byte-identity fixtures (WP7, WP23, WP35) stay green untouched — the capability is
  additive and inert on every run without a translated proposal.
- `tests/test_wp36_translation_guard.py`, committed **first**, pins today's behaviour on the
  miniature of the four cases (`no_hub_for_key`) and the counter-case (surrogate-keyed hub →
  ordinary proposal). The first assertion is *meant* to be flipped by this WP, in the same
  commit that flips it, with the reason in the message; the second must never change.

## 6 Acceptance

Keyless:
1. The four cases become `declared_fk_translated` proposals against the recorded shapes; the
   counter-case does not.
2. A ratified translated proposal yields a link with `key_translation`, a translation model
   whose SQL joins `T` to `R` on `X = Xref` and projects `Y`, a stage model reading it, and a
   `schema.yml` with the two tests.
3. The gate refuses a translation whose `X` is not on `T`; the flag kind appears once per
   applied translation; the checkpoint text names table and columns.
4. Definition of done, plus the existing fixtures untouched.

Live (the WP30 rerun protocol, step 2, cap $20): `adventureworks_incremental`, one repeat, the
§6 conjunction of WP34 measured with the full mechanism — pre-registered prediction ~9
cross-domain links against the bar of 8. n=1 is a direction. If the bar is met, WP34 §6 closes;
if not with the capability built, the falsification clause of the charter applies.

## 7 Not in this WP

- No translation for **composite** keys or for FKs whose `R` has **no** hub (both stay skips).
- No hub re-keying, no alias smuggling, no modeler scope change — the ADR's rejected
  alternatives, rejected here too.
- No second translation hop (`T → R → S`); one join through the referenced relation only.

## 8 Addendum 2026-09-12 — the field leaked into the modeler's schema, the first paid run was aborted

Step 3 (production) of the first WP30 rerun after this WP returned **9 of 23 links carrying
`translations` and `aliases` authored by the modeler**, where the August run's step 3 had none.
Cause: `Link.model_json_schema()` handed `LinkHubRef.key_translation` — docstring included — to
the modeler's tool schema, and the modeler used it (and, encouraged, started filling
`source_key_column` too). `E_LINK_KEY_NOT_IN_SOURCE` fired once on one of them. The run was
stopped in step 4 (~$7 spent on three steps) because it was measuring an LLM-authored
translation mechanism that §2 explicitly rules out ("no judgement").

Two changes, both keyless-tested: the modeler's schema strips `source_key_column`,
`key_translation` and the `KeyTranslation` def (`dv2_modeler._strip_proposer_owned`), and a new
gate `E_LINK_TRANSLATION_UNRATIFIED` refuses any translation not produced by a ratified proposal.
§2's "no judgement" now has a mechanical guard on both ends. The rerun restarts from step 1.

## 9 Stand 2026-09-12, Abend — live once, and the applier is the next wall

§6 live: `link_shopping_cart_item_product` built from a translated proposal in the WP30 rerun,
gate held, flag raised, no modeler-authored translation anywhere. Acceptance items 7–10 (a
`dbt build` of the translation model) remain **open** — the rerun is an LLM eval, not a warehouse
build. Finding: 3 of the 4 cases never reach the applier's link because their referencing tables
are relationship or detail tables without a hub; the translation is correct and unused. That is
not this WP's defect; it is the next capability (relationship-table links), recorded in
`docs/log.md`.
