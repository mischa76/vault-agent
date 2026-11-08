---
type: spec
status: measured
updated: 2026-11-08
---

# WP121 — A payload column whose type has no equality is staged as text (C54)

Status: **Approved and in progress** (2026-11-08, on the owner's go to take up C54 as WP121) · Owner: Mischa Eismann ·
Author: Claude. Candidate C54 (`backlog-2026-11-candidates.md`).

## 1 What is wrong

The twenty-fifth chain's fifth project, built in `aw_source` (log 2026-11-08), failed in every satellite carrying a
PostgreSQL `xml` column: *could not identify an equality operator for type xml*. AutomateDV 0.11.4's satellite merges
its ghost record with the new records by `UNION`, which compares every column (compiled `sat_job_candidate_details`,
read 2026-11-08). The stage hashes the column cast `AS VARCHAR`, so the hashdiff is not affected — the payload
column passed through with its own type is.

**Measured on PostgreSQL 16.15** (`SELECT NULL::t UNION SELECT NULL::t`, 2026-11-08): fails for `xml`, `json`,
`point`, `line`, `lseg`, `box`, `path`, `polygon`, `circle`; works for `jsonb`, `text`, `varchar`, `bytea`, `uuid`,
`money`, `interval`, `tsvector`, `inet`, `cidr`, `macaddr`, `bit`, `varbit`, `numeric`, `integer[]`. Each failing
type cast `AS text` works in the same `UNION`; an `xml` value's text is its serialisation (`resume::text`, 4 543
characters for the first candidate).

## 2 The rule

1. `rules/dv2_rules.py`: `NO_EQUALITY_TYPES` — the nine measured types — and `lacks_equality(declared)`, read through
   the same `_type_base` as `null_safe_type` (case, length and spacing ignored). An unknown word is no evidence.
2. `PlatformProfile.text_type`: the platform's unbounded character type — PostgreSQL `text`, Databricks `string`
   (AutomateDV's `type_string()` is `VARCHAR(255)` on Databricks, which would truncate a document; not used).
3. The staging generator: for a **bound** stage, every declared column of the bound relation whose type
   `lacks_equality` becomes a derived column of the same name, `CAST(<COL> AS <text_type>)`. AutomateDV excludes a
   source column of a derived column's name (`stage.sql`, `exclude_column_names`) and hashes after deriving, so the
   satellite reads text and the hashdiff is the one it was. Recorded in `automatedv.yml`'s `derived_columns` as
   every derived column is.
4. Not touched: an inferred stage (no declared types); a column the spec already derives under that name; a
   reserved-word column (WP79's escaping form takes a column, not an expression — a reserved name of such a type is
   flagged in the spec's §5 as not done). A relation without such a type renders byte-identically.

## 3 Not done

Types the warehouse may lack equality for on platforms the generator does not target (SQL Server's `geography`,
`geometry`, `text`); a cast for hub or link keys of such a type (a key of type `xml` is no key); the profiler's
refusal of `xml` statistics (WP98, *UndefinedFunction*) — separate.

## 4 Pre-registration

- **P1** guards T1–T5 (`tests/test_wp121_no_equality_types.py`) committed red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable; any older guard that changes is one whose fixture
  declares one of the nine types, named in §5 with its reason.
- **P3 differential rebuild, keyless.** The fifth project of the twenty-fifth chain regenerated from its saved state
  before and after the change (`CodeGeneratorAgent` on `state.json`): the only files that differ are the stages
  reading `JobCandidate`, `Person`, `Illustration`, `ProductModel` and `Store` (and `automatedv.yml`), each gaining
  a derived cast per `xml` column. Those files copied over the run's own project, built in `aw_source` into a fresh
  schema: **PASS=420 ERROR=1 SKIP=4** of 425 — the five satellites and the two PITs behind them build, the
  remaining error and skips are `stg_product_subcategory`'s (inferred, C39). Each of the five satellites holds one
  row per source row plus the ghost record.
- **Not predicted:** whether the regeneration from the final state equals the run's project elsewhere (it does not —
  zero-key sources and expected-column comments differ, seen before the change; the differential reads only what
  WP121 changes).

## 5 Measured (2026-11-08, keyless)

- **P1 ✔.** T1–T5, 24 guards, red by import at `1b87a07`. Two fixture corrections before green, both the guard's
  premise and not the rule: the stage under test is the satellite's own (`stg_job_candidate_details`, the one that
  hashes the hashdiff), and T5 reads a relation the catalogue lacks — without any catalogue a run is ungrounded and
  its stages count as declared, and a satellite with a `source_table` binds verbatim (never inferred), so the
  premise „inferred" holds for the hub's stage only; T5 now asserts both stages uncast.
- **P2 ✔.** Suite with no key reachable 1674 passed / 5 skipped (1650 + 24), ruff, bare mypy. No older guard
  changed: no fixture's bound relation declares one of the nine types in a way a pinned output reads.
- **P3 ✔ exactly as pre-registered.** Regenerated before (`replay0`) and after (`replay1`): the only differing files
  are `automatedv.yml` and the nine stages reading `JobCandidate` (2), `Person`, `Store`, `Illustration` (2) and
  `ProductModel` (3), each gaining `derived_columns` with one `CAST(<col> AS text)` per `xml` column. Those nine
  were byte-identical between `replay0` and the run's own project, so they were copied over a copy of the run's
  project; built in `aw_source` into a fresh schema: **PASS=420 WARN=0 ERROR=1 SKIP=4** of 425 — the error and
  skips `stg_product_subcategory`'s. Rows: `sat_job_candidate_details` 14 (13 + ghost), `…_person_sensitive`
  19 973 (19 972 + 1), `…_store_demographics` 702 (701 + 1), `sat_illustration_details` 6 (5 + 1),
  `sat_product_model_content` 129 (128 + 1); `pit_business_entity` 62 337 and `pit_product_model` 390 rows; the
  satellite's `resume` is `text` and equals the source's `resume::text` for 13 of 13 candidates.
- **Not measured:** Databricks (the cast's spelling is guarded, not built); the regeneration from the final state is
  not byte-identical with the run's project elsewhere (zero-key sources, expected-column comments) — seen before the
  change, outside this WP; the measurement schema dropped afterwards.
