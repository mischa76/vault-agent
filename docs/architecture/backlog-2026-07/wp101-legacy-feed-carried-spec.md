---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP101 — The grandfathered feed stays grandfathered on every later step, and the satellite it carried stays with it (C34, C35)

Status: **Approved and in progress** (2026-10-30, the owner's go after WP100: C34 and C35 together, both hang on the
multi-source hub) · Owner: Mischa Eismann · Author: Claude. Found by the C1 experiment's keyless PostgreSQL build of
arm A's fifth project (`docs/log.md`, 2026-10-30, „The audit the plan put first").

## 1 What is wrong, in one paragraph

`hub_unit_measure` was single-source in step 3 with `sat_unit_measure_details` (no `source_table`) reading
`stg_unit_measure`. Step 4 added `ProductVendor` as a second feed: the merger materialised the legacy feed, WP23 §2.6
grandfathered its stage under the old name, and the existing satellite was — rightly — not split and kept reading
`stg_unit_measure`. Step 5 lost all of it: `legacy_feeds` derives the grandfathered feeds from the *immediately
preceding* model only and deliberately excludes a hub that is already multi-source there (a hub multi-source from
greenfield must keep its symmetric names), so the legacy feed's stage was renamed `stg_unit_measure_unitmeasure` —
the rename of a materialised model that §2.6 exists to refuse — while the existing satellite's SQL still named
`stg_unit_measure`, and dbt refused the project on the missing node (**C34**). Independently, the staging generator
never learned §2.6's rule for existing satellites: from step 4 on it put the satellite's payload into *every* feed's
stage, so `stg_unit_measure_productvendor` hashed `NAME`, which `ProductVendor` does not have (**C35**). The raw-vault
generator and the staging generator disagreed about where an existing satellite lives — the WP24 class.

## 2 The rules

1. **The catalogue says which feed is grandfathered.** `legacy_feeds(existing, carried_bindings)`: as today for a hub
   that was single-source in the existing model; and for a hub *already* multi-source there, the feed whose table the
   carried catalogue binds `stg_<entity>` to (`stage_bindings`, WP77; normalised; exactly one feed must match). The
   catalogue is the record of what is materialised under which name; the model alone cannot tell a grandfathered
   feed from a greenfield feed that happens to be named like the hub's entity. No binding carried under that name →
   nothing grandfathered, as today.
2. **An existing satellite without `source_table` on a hub with a legacy feed belongs to that feed — in staging too.**
   The raw-vault generator already renders it once, unsplit (WP23 §2.6); the staging generator now puts its payload
   and hashdiff into the legacy feed's stage only. Both sides name that stage through `multi_source_staging_name`
   of the same `legacy_feed_of(hub, legacy)`, so they cannot disagree.
3. **Not identifiable, not guessed.** When the hub is multi-source and no legacy feed is identifiable, an existing
   satellite without `source_table` is flagged (`GENERATION_GAP`, the satellite as asset: the stage it read cannot be
   found among the hub's feeds, the carried catalogue binds no `stg_<entity>`) and not rendered; no stage carries its
   payload. Rendering it against `stg_<entity>` as before produced an unparseable project; rendering it against a
   feed would be a guess; splitting it is the migration §2.6 refuses.
4. **The project's own check sees the raw vault.** `unresolved_raw_vault_refs`: every raw-vault model's
   `source_model` (bare or list) and every `ref()` in it must name a rendered staging or raw-vault model;
   `project_self_contained` fails on it as it fails on an unresolved staging relation (WP74). The eval would have
   caught C34 at step 5 without a build.
5. **Unchanged:** greenfield naming (no existing model, nothing grandfathered); a hub single-source in the existing
   model (today's derivation); new satellites on a multi-source hub (WP10 split, ADR-0011 row 1); feed-bound
   satellites (ADR-0011 row 2); the step N+1 shape's raw-vault output (the existing test's assertions hold).
6. **Not in this WP:** a gate refusing a hub feed stage that hashes a column its bound relation lacks (WP73 refuses
   it for link stages) — with rule 2 the shape has no producer left here; a legacy feed whose stage was inferred
   (`raw_<entity>`, not in `stage_bindings`) stays unidentifiable on the step after next and lands in rule 3.

## 3 Acceptance (keyless)

`tests/test_wp101_legacy_feed_carried.py`, committed red before the change: `legacy_feeds` reads the carried binding
for an already-multi-source hub and nothing else (no binding, a binding to a non-feed, a suffixed binding: empty);
on the step-after-next shape the legacy stage keeps its name, the existing satellite reads it and the hub's list
names it; the existing satellite's payload is in the legacy feed's stage and in no other, on step N+1 and N+2; without
a carried binding the satellite is flagged, not rendered, and no raw-vault model names an unrendered stage;
`unresolved_raw_vault_refs` names a model reading an unrendered stage in all three forms; the scorer fails on it.
`tests/test_brownfield_extension.py` unchanged.

## 4 Pre-registration (keyless, PostgreSQL 16, the local data copy)

Arm A's fifth project (`20261030T184653194084Z`, step 5) regenerated from its kept artefacts — the step's model, the
sales increment's declared schema, the fourth step's model and catalogue as `--existing` reads them (its
`stage_bindings` carry `stg_unit_measure: UnitMeasure`), the step's mapping proposals — through the code generator
and the mapper's re-bind, built into a fresh schema `c1_a_wp101`:

- **P1** against the kept project: `stg_unit_measure_unitmeasure` is gone and `stg_unit_measure` is back, bound to
  `UnitMeasure`; `stg_unit_measure_productvendor` no longer hashes `UNIT_MEASURE_DETAILS_HASHDIFF` nor projects
  `NAME`; `hub_unit_measure.sql` lists `stg_unit_measure`; `sat_unit_measure_details.sql` is byte-identical to the
  kept file; every other staging and raw-vault model is byte-identical. A difference beyond these is listed.
- **P2** `dbt parse` succeeds without the hand view; `dbt build` has exactly the two inferred-stage errors (C18:
  `raw_business_entity_purchase_order_ship_method`, `raw_product_component_unit_measure`) and their dependents as
  skips, nothing else; `stg_unit_measure_productvendor` builds.
- **P3** `sat_unit_measure_details` holds 38 rows (the `UnitMeasure` relation's 38), every `unitmeasure_hk` joins
  `hub_unit_measure`; `hub_unit_measure` holds the distinct `UnitMeasureCode` values of `UnitMeasure` ∪
  `ProductVendor` plus WP86's zero-key rows.
- **P4** `project_self_contained`, recomputed with rule 4 on the kept step-5 artefacts, is 0.0 and names
  `sat_unit_measure_details`; on the regenerated project it is 1.0.
- **P5** `uv run pytest` green, no fixture updated.

Not predicted: wall time; the PASS total.
