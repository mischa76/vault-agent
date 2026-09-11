---
type: spec
status: keyless-only
updated: 2026-09-11
---

# WP35 — Databricks as a selectable target platform

Status: **Built, keyless-only** (2026-09-11, Claude) · Requested 2026-09-11 (Mischa: „bau die
Databricks-Unterstützung ein, erstmal keyless") · Owner: Mischa Eismann
Depends on: WP7 (seed column types from contracts — the only platform-specific output the
generator has), ADR-0003 (AutomateDV as the backend; its platform list already names
Databricks). Supersedes nothing. No ADR: the platform decision is ADR-0003's, this WP makes one
of its listed platforms selectable.

## 1. Problem

The generated project has always claimed to run on "any AutomateDV-supported warehouse", and
the vault SQL does — every physical difference is dispatched per adapter inside the package.
One artifact is not neutral: the seed column types written into `dbt_project.yml` when a data
contract pins a staging source's types (WP7 §7.3). They were spelled the Postgres way, and on
Databricks two of the six spellings are wrong in different ways:

- `varchar` without a length is not the platform's native character type (that is `STRING`);
- `numeric` without precision **is accepted and silently truncates** — the SQL reference
  documents `DECIMAL`'s default as `p=10, s=0`
  (learn.microsoft.com/azure/databricks/sql/language-manual/data-types/decimal-type). A
  contract saying "number" for a balance would load `1234.56` as `1235`. That is a data
  defect, not a syntax error, and exactly the class this project treats as the only one that
  matters (CLAUDE.md, the `rules/` helper invariant).

A "just point profiles.yml at Databricks" story therefore needed a dialect, not a switch.

## 2. Verified before designing

Read in the installed package and the published metadata, not remembered:

- **AutomateDV 0.11.4 implements every macro the generator calls for Databricks.**
  `macros/tables/databricks/` holds `hub`, `link`, `sat`, `eff_sat` (with
  `is_auto_end_dating`), `t_link`, `ma_sat`; `stage` dispatches through `adapter.dispatch`
  with `default__stage` and no Databricks override. Pinned as a test that reads the package
  (`tests/test_target_platform.py`, skipped when `dbt deps` has not run).
- **The generator writes no Postgres SQL.** `grep` over `code_generator.py` and
  `staging_generator.py` finds no casts, no timestamp functions, no adapter-specific
  configuration; the Postgres references are comments and the seed-type table.
- **The dbt pin holds.** `dbt-databricks` 1.9.x requires `dbt-core >=1.8.7,<1.10.14`
  (PyPI metadata, 1.9.8), i.e. the same 1.9 line the Postgres demo is verified on — the dbt
  bump the 2026-08-24 log entry deliberately avoided is not needed. `uv lock` resolved the new
  extra to `dbt-databricks 1.9.7` with `dbt-core 1.9.10` unchanged.
- **No workspace is available on this machine.** No Databricks configuration, no environment
  variables. Everything below is keyless.

## 3. Design

**One place knows platforms: `src/vault_agent/rules/platforms.py`.** A `TargetPlatform`
Literal, a `PlatformProfile` per member (adapter package, profile type, the seed-type dialect,
one README hint), and an import-time check that the Literal and the profile table agree and
that every profile translates every abstract seed type. Adding a platform is one profile plus
a pinned fixture; it is *not* a claim of verification — which platforms have been built against
live is a dated statement in the operations manual (9.6), never in code.

**The abstract seed types stay spelled the Postgres way.** That output predates the dialects and
is pinned byte-for-byte; the Postgres profile is the identity, so the renderer has no special
case for the default and the WP7 guard keeps proving inertness.

**The Databricks dialect:** `varchar→string`, `numeric→decimal(38,18)`, the rest unchanged.
38 is the platform maximum precision; 18 fractional digits leave 20 integer digits. This is a
deliberate wide default named once (`DATABRICKS_UNSCALED_DECIMAL`), not a guess per call — the
contract spec carries no precision/scale, so the generator has nothing better to read. When it
does, the profile is where that reading lands.

**The choice is run state.** `VaultAgentState.target_platform` (default `postgres`), set by
`vault-agent run --target-platform <name>` and persisted in the checkpoint, so a paused run
resumes on the platform it started on without re-passing the flag — the same reasoning as
`--existing`. Both `build_staging` call sites (code generator, source-mapper rebind) pass it
through; nothing else branches on it.

**Output that differs for a non-default platform:** the `+column_types` values, and one
README section naming the platform, the adapter and the profile shape. The default's README
still says "any AutomateDV-supported warehouse", which stays true.

**Dependencies:** a `demo-databricks` extra (`dbt-core~=1.9.0`, `dbt-databricks~=1.9.0`),
separate from `demo` because it drags in dbt-spark and the SQL connector.

## 4. Not done, deliberately

- **No live build.** `demo/bank_databricks/` does not exist. It needs a workspace with a SQL
  warehouse and a token; the Free Edition suffices. Until it runs, "runs on Databricks" is a
  keyless claim and is worded as such everywhere.
- **No incremental-strategy setting.** dbt-databricks' default `merge` without a `unique_key`
  should insert every row (append semantics), which is what AutomateDV's incremental models
  expect. Not verified; writing `+incremental_strategy: append` into the generated project
  would encode an unverified belief. It is the first thing the live run checks.
- **No other dialects.** Snowflake, BigQuery and SQL Server remain reachable the old way:
  default platform, Postgres-spelled seed types, which those platforms happen to accept.
  They get a profile when someone verifies one.
- **No `TIMESTAMP_NTZ`.** Databricks `TIMESTAMP` carries the session time zone; AutomateDV's
  Databricks macros work on `TIMESTAMP`, and the load-date semantics are the same as on
  Postgres for a single-zone load. Revisit if a live run shows zone drift.

## 5. Acceptance

Keyless (met 2026-09-11, `tests/test_target_platform.py`):

1. Default run output byte-identical to before — the WP7 and WP23 guards plus an explicit
   "default equals postgres" test.
2. Raw-vault and staging SQL identical across platforms; only scaffolding differs.
3. Databricks seed types as specified; `varchar` absent; the fixture under
   `tests/fixtures/staging_databricks_baseline/` pins the scaffolding.
4. The platform survives the source-mapper rebind.
5. `--target-platform` is listed, an unknown value fails with a usage error before any model
   call, the state model refuses an unknown value.
6. Every called macro has a Databricks implementation in the installed AutomateDV.

Live (open — needs a workspace):

7. `dbt deps && dbt build --full-refresh` green on the bank model with seeds.
8. A second plain `dbt build` is idempotent (row counts unchanged).
9. The effectivity satellite closes a superseded relationship (the two-phase end-dating
   demo, 9.4).
10. `BALANCE` loads with its fractions intact — the one assertion this WP was written for.

## 6. Open questions the live run answers

- Does dbt-databricks' default incremental strategy behave as append without a `unique_key`
  under AutomateDV's `incremental` models? If not, the profile gains a
  `dbt_project_overrides` and `+incremental_strategy: append` becomes generated output.
- Identifier casing: the seeds are `+quote_columns: false`; Databricks resolves identifiers
  case-insensitively, so UPPER_SNAKE should fold like on Postgres. Check the first build's
  column resolution before anything else, as 9.6 predicts for every new platform.
- Unity Catalog: `catalog` in the profile vs. a `+catalog`/`database` in the generated
  sources — grounded runs with a `database` on the declared table need a mapping decision.
