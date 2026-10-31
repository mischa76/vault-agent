---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP107 — `dbt_project.yml` carries a `seeds:` block, and seed column types, only for stages that read a seed (C10)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog, C10 first) · Owner: Mischa Eismann ·
Author: Claude. C10 is from the owner's own build (2026-10-20: „dbt warns of 7 unused paths").

## 1 What is wrong

The scaffolding writes a `seeds:` block into every `dbt_project.yml` — `+quote_columns: false` for the project and,
where a drafted contract matches a stage's relation by name, a `+column_types` entry per relation (WP7 §7.3). The
block is right in the seed world (ungrounded runs, the bank demos: every stage reads `seeds/<name>.csv`). In a
grounded project every stage reads a declared relation through `source()` (WP7 §7.2) or the `inferred` block (WP76),
and nothing reads a seed; dbt then warns on every parse and build that the paths apply to no resource — the owner's
Sales step types 17 relations it reads through `source()` (demo run `20261022T234439976097Z`), the twenty-third chain's
fifth project carries the bare block (`seeds.vault_project`, one warning). A warning on every build of every grounded
project is noise a user learns to ignore, which is how the next real warning is missed.

## 2 The rules

1. **A stage reads a seed when it reads a bare name no block declares** — `StagingSpec.source_name is None` after the
   blocks are assigned: no `source()` block (the relation was declared without a physical location, or nothing was
   declared) and not the `inferred` block. A declared table without `schema`/`database` is seed-compatible by WP7's
   design and stays one.
2. **The `seeds:` block is written only when some stage reads a seed**, and its `+column_types` entries only for the
   relations those stages read. A project whose stages all read sources carries no `seeds:` key at all.
3. **Nothing else moves.** The staging models, `sources.yml`, `packages.yml` and the README are untouched (the README's
   „`dbt seed` (if using seeds)" already says it). The ungrounded and the Databricks byte-identity baselines are
   unchanged — the seed world is the seed world.

## 3 Not this WP

Removing the seed column-type mechanism (WP7 §7.3) — it is right where seeds are read. Regenerating the demo's frozen
runs (they reproduce a recorded run). A contract matched by name to a `source()` relation is still drafted; only the
unused seed typing of it goes.

## 4 Acceptance (keyless)

`tests/test_wp107_seed_block_only_for_seeds.py`, committed red (four of six; the ungrounded and the bare-declared pins
green): an ungrounded project keeps its block and types; a grounded project reading sources only has no `seeds:` key
even with a matching typed contract; a bare-declared table keeps its types; a mixed project types only the seed-read
relation; an inferred stage in a grounded project is no seed; the demo's Sales step replayed (WP95's `_replayed`)
types no seed.

## 5 Pre-registration (keyless)

- **P1** The twenty-third chain's fifth project (WP106's re-chained step 5) regenerated after the change: `dbt_project.yml`
  loses exactly the six-line `seeds:` block and nothing else (`diff`); `dbt parse` and `dbt build` logs carry no
  „Configuration paths exist" warning (the kept build: one, `seeds.vault_project`); build PASS=421 of 421 unchanged.
- **P2** The demo's Sales step replayed: the 17 `+column_types` entries and the block gone (the guard).
- **P3** Suite green with the two byte-identity baselines untouched; the bank demos (seed world) unchanged; ruff, bare
  mypy.

## 6 Measured

Appended after the run.

## 6 Measured (2026-10-31, keyless; PostgreSQL 16, the local copy, dbt 1.9.10, AutomateDV 0.11.4)

- **P1 ✔.** WP106's re-chained fifth project regenerated after the change: `diff -r` against the mirrored project
  names `dbt_project.yml` alone — the `seeds:` block gone (seven lines with its leading blank line; §5 said six),
  nothing else; `dbt parse` and `dbt build` in the fresh schema `c38s`: **0** warnings of any kind (the kept build: one,
  `seeds.vault_project`), **PASS=421 WARN=0 ERROR=0 SKIP=0 TOTAL=421**. Schema dropped.
- **P2 ✔.** The demo's Sales step replayed through WP95's `_replayed`: no `seeds:` key, no `+column_types` (the
  recorded run: 17 typed relations, all read through `source()`).
- **P3 ✔.** Suite 1465 passed, 5 skipped (6 new); the ungrounded and the Databricks baselines byte-identical (their
  guards unchanged); the bank demos untouched; ruff, bare mypy.
- **Guards.** Four of six red before the change as §4 says, after two corrections to the fixture itself, both
  committed before the change: the contract field named like the column (`CustomerID`; the label `Customer ID`
  normalises to `CUSTOMER_ID` and the pin was red on its own label), and the inferred-stage fixture — a satellite
  naming `source_table: Product` is a *declared* binding (WP7 §7.1), rendered as a bare name even when no such table
  is declared, and a bare name is seed-compatible by rule 1; the guard now leaves that satellite without a
  `source_table`, so the hub's stage is the inferred `raw_product` under WP76's block, which is no seed.
