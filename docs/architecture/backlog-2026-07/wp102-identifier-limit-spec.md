---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP102 — A translation model's name stays within the platform's identifier limit (C36)

Status: **Approved and in progress** (2026-10-30, the owner's go: C36 after C34/C35) · Owner: Mischa Eismann · Author:
Claude. Found by WP100's keyless PostgreSQL build of arm T's fifth project (`docs/log.md`, 2026-10-30).

## 1 What is wrong, in one paragraph

`translation_model_name` joins every translated relation into `stg_<link>_via_<a>_and_<b>_and_…`. Arm T's fifth
project names one view 74 and one 103 characters long
(`stg_culture_product_description_product_model_via_productmodel_and_culture`,
`stg_sales_order_customer_via_customer_and_creditcard_and_currencyrate_and_shipmethod_and_salesterritory`);
PostgreSQL's identifiers end at 63 (`SHOW max_identifier_length` on the house server: 63), dbt-postgres refuses the
relation outright (`Relation name … is longer than 63 characters`), and the stage reading it, its tests and its link
are skipped. The platform profile (`rules/platforms.py`) carries no identifier length, so nothing could have known.
WP100's collision had hidden it: the project never parsed before.

## 2 The rules

1. **The platform profile knows its identifier limit.** `PlatformProfile.max_identifier_length`: PostgreSQL 63
   (verified on the server), Databricks 255 (Unity Catalog: „Object names cannot exceed 255 characters",
   learn.microsoft.com/azure/databricks/sql/language-manual/sql-ref-names, read 2026-10-30). Adding a platform
   means stating its limit.
2. **A translation model's name that would exceed the limit is shortened deterministically.** The full
   `stg_<link>_via_<a>_and_<b>…` name is kept whenever it fits — every existing output is byte-identical. When it
   does not, the name is `stg_<link>_via_<n>_<digest>`: the count of joined relations and six hex digits of a
   SHA-256 over the joined list, so two links through different tables never share a name and the same list always
   yields the same one. The joined relations stay readable where they already were: the view's header comment,
   its `schema.yml` description and the stage entry's `key_translation.joins` in `metadata/automatedv.yml`.
3. **Every staging model name is checked at render time.** A name over the limit after rule 2 — a link or hub whose
   own name is too long for the platform — is flagged (`GENERATION_GAP`, the model as asset, the length and the
   limit in the message), not truncated: a truncated name is a different model than every reference to it.
4. **Unchanged:** the raw-vault construct names (the modeler's; `E_BAD_NAME` gates their shape, not their length —
   a gate with a remedy is the right tool there and is not this WP); names that fit; the single-translation form.

## 3 Acceptance (keyless)

`tests/test_wp102_identifier_limit.py`, committed red: the two profiles' limits; the long name shortened under 63 and
kept under 255, deterministic, distinct for a different list; a built project on PostgreSQL names the view, the
stage's `source_model` and the `schema.yml` by the short name and still lists every joined relation in the header; a
staging name over the limit is flagged on PostgreSQL and not on Databricks. The rest of the suite unchanged.

## 4 Pre-registration (keyless, PostgreSQL 16, the local data copy)

Arm T's fifth project regenerated as for WP100 (now with WP100, WP101 and this WP), built into `c1_t_wp102`:

- **P1** against the kept project the staging differs in WP100's fifteen files and in nothing else, except that the
  two long views and their `schema.yml` now appear under short names of at most 63 characters.
- **P2** `dbt parse` succeeds; `dbt build` has exactly two errors — the inferred stage
  `stg_location_product_work_order` (C18) and `stg_product_product_review_via_product` (the data copy's `text`
  `productid`, an artefact) — and their dependents as skips; the culture and sales-order stages, links and tests
  build.
- **P3** WP100's two unmeasured links: `link_culture_product_description_product_model` holds
  `ProductModelProductDescriptionCulture`'s row count and `link_sales_order_customer` holds `SalesOrderHeader`'s;
  in each, every pushed-apart hub key joins its hub (0 orphans) and 0 rows carry two equal hub hashes.
- **P4** `uv run pytest` green, no fixture updated.

Not predicted: wall time; the PASS total.
