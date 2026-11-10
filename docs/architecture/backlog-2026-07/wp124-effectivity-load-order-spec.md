---
type: spec
status: measured
updated: 2026-11-10
---

# WP124 — Effectivity satellites: the load-order precondition stated, and a generated test that fails when it was broken (C62, options a + b)

Status: **Approved and in progress** (2026-11-10, the owner chose (a)+(b); (c), an effectivity model of vault-agent's
own, stays in C62) · Owner: Mischa Eismann · Author: Claude. Candidate C62.

## 1 What is wrong

C60 measured (P6): the bank demo's effectivity satellite, batch 2026-04-01 loaded before 2026-01-01, ends with ACC-503
held by two owners at once and a record whose end (01-01) precedes its start (04-01). AutomateDV's `eff_sat` assumes
batches in load order; nothing in a generated project says so or notices when it is broken.

## 2 The rules

1. **(a)** A generated project with at least one effectivity satellite carries a section in its `README.md`: batches
   must be loaded in load order; what goes wrong otherwise; that the generated tests below catch it. A project
   without one is byte-identical.
2. **(b)** Per effectivity satellite two singular dbt data tests in `tests/` (the project's `test-paths`):
   - `<sat>__one_open_per_driving_key.sql` — per relationship (the link hash key) the latest row by load date; of
     those, the open ones (`automate_dv.cast_date(end) = automate_dv.cast_date(max_datetime())`, AutomateDV's own
     definition, `eff_sat.sql:72`); fails when a driving key (all driving-key columns) has more than one;
   - `<sat>__end_after_start.sql` — fails on any row whose end date precedes its start date.
   Both read the satellite's metadata (`src_pk`, `src_dfk`, `src_start_date`, `src_end_date`, `src_ldts`), so a
   driving key of several columns groups by all of them. `dbt build` runs them.

## 3 Not done

(c) — an effectivity model rebuilt from the link history, which makes load order irrelevant; repairing a satellite
the tests caught (the README says: rebuild with `--full-refresh`, in order).

## 4 Pre-registration

- **P1** guards (`tests/test_wp124_effectivity_load_order.py`) red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable; the greenfield manifest (the bank model has an
  effectivity satellite: `README.md` changes, two test files appear) and the ungrounded baseline's `README.md`
  regenerated deliberately; no raw-vault or staging model changes.
- **P3** C60's bank part with the two generated tests copied in: **reversed** batches → `one_open_per_driving_key`
  fails with exactly one row (ACC-503's driving key, 2 open) and `end_after_start` fails with exactly one row
  (CH-1002, 04-01 → 01-01); **in order** → both pass.
- **P4** the twenty-fifth chain's fifth project: its effectivity satellites gain two tests each; regenerated and
  overlaid as in WP123, built: every new test passes (one full load is in order), the rest as before
  (PASS rises by twice the number of effectivity satellites, ERROR=1 SKIP=4).

## 5 Measured (2026-11-10, keyless)

- **P1 ✔.** Five guards, red at `bd1b679`, green after.
- **P2 ✔.** Suite with no key reachable 1724 passed / 5 skipped, ruff, bare mypy. Changed deliberately: the
  ungrounded baseline's `README.md` and its two new test files, the greenfield manifest (`README.md`, `report.html` —
  its file list names the two tests — and the two tests added), `test_agent_wires_staging_into_artifacts_and_metadata`
  (the bank model's scaffolding gains the two tests). No raw-vault or staging model changed.
- **P3 ✔ exactly.** C60's bank part with the generated tests (`eval/automatedv/scenario.py`, extended): reversed
  batches → `one_open_per_driving_key` FAIL with 1 row, `end_after_start` FAIL with 1 row; reloaded in order → both
  PASS with 0 rows.
- **P4 ✔.** The twenty-fifth chain's fifth project regenerated: no model differs from WP123's, three effectivity
  satellites gain six tests; overlaid on the WP123 build: **PASS=426 ERROR=1 SKIP=4** (420 + 6), every new test
  passing.
- **Not measured:** Databricks (the tests use AutomateDV's own date macros, dispatched per adapter).
