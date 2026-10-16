---
type: spec
status: not-measured
updated: 2026-10-16
---

# WP72 — Databricks, live: the bank demo built on a real workspace (stage 1 of 3)

Status: **Approved and in progress** (2026-10-16, user: „für databricks wurde der Grundstein
ja bereits gelegt, wie wäre es wenn man hier mal die volle Kette als Beweis dazu nimmt?“, the
workspace created the same day) · Owner: Mischa Eismann · Author: Claude. Takes WP35's open
acceptance 7–10 and its §6 questions to a real build. Stages 2 (the person step) and 3 (the
five-step chain) follow on their own „go“ and their own entries.

## 1 Scope

`demo/bank_databricks/` — the twin of `demo/bank_postgres/` aimed at Databricks: the same
model, the same seeds, the same hand-authored staging and test properties, the seed types in
the Databricks dialect from `rules/platforms.py`, a `profiles.yml` that reads host, HTTP path
and token from the environment (`.env`, never committed), catalog `workspace`, schema
`default`. A second uv environment (`.venv-databricks`, `--extra dev --extra demo-databricks`),
because that extra excludes `demo`. Then the live build on the owner's Free Edition workspace.

## 2 The rules

1. **No second model, no second SQL.** The raw-vault models are written by the same
   generator (`build_vault_models.py` imports the Postgres demo's model and generates with
   `target_platform="databricks"`); WP35 proved the SQL identical across platforms, and a
   guard keeps every `.sql` under the twin byte-identical to the Postgres demo's. What differs
   is `dbt_project.yml` (name, profile, seed types) and `profiles.yml`.
2. **The seed types come from the dialect**, never typed by hand: each `+column_types` value
   is `platform_profile("databricks").seed_type(<the Postgres demo's type>)`.
3. **Secrets stay in the environment.** `profiles.yml` uses `env_var()` for host, HTTP path
   and token; catalog and schema are `env_var()` with defaults. dbt is run through
   `uv run --env-file .env`.
4. **The demo checklist is the acceptance**, the same as on Postgres (chapter 9.5) plus the
   two Databricks checks chapter 9.6 names.

## 3 Guards before the change (keyless)

1. The twin's `models/**/*.sql`, `_raw_vault.yml`, `seeds/*.csv` and `packages.yml` are
   byte-identical to the Postgres demo's; `dbt_project.yml` names `bank_databricks`, keeps
   `+quote_columns: false`, and every seed column type is the dialect's translation of the
   Postgres demo's — no `varchar`, no bare `numeric`.
2. `profiles.yml` is `type: databricks`, reads the three connection values through
   `env_var`, carries no literal token, and defaults catalog/schema to `workspace`/`default`.
3. The twin's `build_vault_models.py` regenerates the raw-vault models with the Databricks
   platform into a temporary directory and they equal the committed ones.

## 4 Pre-registration (live, the owner's workspace)

On the Free Edition's 2X-Small serverless warehouse, from the twin's directory with
`DBT_PROFILES_DIR=.`:

- **L1** `dbt deps` fetches AutomateDV 0.11.4; `dbt build --full-refresh` ends
  `PASS=29 WARN=0 ERROR=0` as on Postgres (6 models, 3 staging views … the same counts), or
  the difference is named.
- **L2** a second plain `dbt build` is idempotent: every incremental model inserts 0 rows,
  the row counts of the six vault tables are unchanged (3 / 4 / 5 / 3 / 4 / 5).
- **L3** Phase B2: the two-batch load closes CH-1001 on ACC-503 at 2026-04-01 and leaves
  CH-1002 open — the effectivity satellite's end-dating.
- **L4** `BALANCE` of ACC-501 reads back as 250.50, fractions intact (WP35's reason to exist).
- **Q1–Q3** (WP35 §6): whether dbt-databricks' default incremental strategy appends without a
  `unique_key` (L2 answers it); whether UPPER_SNAKE identifiers fold as on Postgres (the first
  build's column resolution); how Unity Catalog's `catalog` relates to the generated sources
  (the profile's `catalog` suffices for seeds; declared sources are stage 2's question).

Expected cost: none (Free Edition), one fair-use day. Not predicted: wall time.

## 5 Not in this WP

The person step and the chain (stages 2 and 3); a `+incremental_strategy` in generated output
unless L2 says it is needed; Snowflake or Fabric; any change to `rules/platforms.py` unless
the live build contradicts the dialect.

## 6 Results

*(appended after the change)*

**2026-10-16 — stage 1 built and verified live.** Guards `47e9192` (red), the twin `05405ba`,
docs in the commit carrying this line. Workspace: the owner's Free Edition, serverless
2X-Small warehouse, catalog `workspace`, schema `default`, DBSQL 2026.39; adapter
dbt-databricks 1.12.5 on dbt-core 1.11.15 (`.venv-databricks`); AutomateDV 0.11.4. **L1 held:**
`dbt build --full-refresh` — `PASS=36 WARN=0 ERROR=0` in 76 s (7 incremental models, 4 seeds,
21 tests, 4 views; the Postgres README's 29 predates WP8's transfer link). Row counts 3 / 4 / 5 /
3 / 4 / 5 and `link_transfer` 3, the Postgres figures. **L2 held:** a plain `dbt build`
`PASS=36`, every count unchanged. **L3 held:** after the two-batch load CH-1001 on ACC-503 is
closed at 2026-04-01 (the current row), CH-1002 open, the satellite 6 rows. **L4 held:**
`BALANCE` of ACC-501 reads 250.500000000000000000 as `decimal(38,18)`; the seeds are typed
`string` / `decimal(38,18)` / `timestamp`. **Q1:** without a `unique_key` dbt-databricks runs
`merge … on FALSE … when not matched then insert *` — every source row is inserted, nothing
updated; with AutomateDV's own new-row filter the second build inserts nothing. Append semantics
hold; no `+incremental_strategy` is needed. **Q2:** the stored column names are UPPER_SNAKE as
emitted (`ACCOUNT_HK`, `ACCOUNT_NUMBER`, …) and resolve case-insensitively — the Postgres
convention carries over unchanged. **Q3:** the profile's `catalog` is enough for seeds and
models (`workspace.default.hub_account`); declared sources remain stage 2's question. One dbt
deprecation warning (a custom config key on the effectivity satellite, `is_auto_end_dating`) —
AutomateDV's, not ours. Cost: none; wall ≈ 5 min of warehouse time in all.
