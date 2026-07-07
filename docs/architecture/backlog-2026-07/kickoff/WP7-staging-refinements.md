# Kick-off WP7 — Staging refinements

You are a senior data engineer with dbt/AutomateDV expertise working on **vault-agent**
(this repository). Your task is exactly one work package with three sub-items; one commit
per sub-item, in spec order.

## Read first, in this order
1. `CLAUDE.md` — repo canon, especially the staging-generator milestone paragraph
   (2026-07-06) and its recorded deferrals — those deferrals are this WP.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp7-staging-refinements-spec.md` — your spec.
4. `src/vault_agent/agents/staging_generator.py` (all),
   `src/vault_agent/agents/code_generator.py` (`_render_sat`/`_render_ma_sat`, the
   staging integration at the end of `run`), `src/vault_agent/state.py` (`Satellite`,
   `SourceTable`), `src/vault_agent/source_schema.py`,
   `src/vault_agent/agents/validator.py` (warning-gate pattern),
   `demo/bank_postgres/models/staging/` (the verified reference output),
   `tests/test_agents/test_staging_generator.py`.
5. AutomateDV stage-macro docs for the `source_model` mapping form — verify against the
   pinned version (`rules.AUTOMATE_DV_VERSION`), not memory.

## Task
§7.1 `Satellite.source_table` + own staging spec for finer-grain ma_sats +
`W_MASAT_SHARED_GRAIN` · §7.2 `source()`-bound staging + real sources.yml on grounded
runs (SourceTable `schema_name`/`database`) · §7.3 contract-driven seed `column_types`.

## Constraints
- Ungrounded output must stay byte-identical (regression test is part of the spec —
  write it first).
- The graph order (data_contract before code_generator) is what makes §7.3 possible —
  do not reorder nodes.
- Inferred bindings keep their `SOURCE_BINDING` flag; declared bindings never flag.

## Definition of Done
Spec acceptance criteria 1–4 verified · `uv run pytest -q` / `ruff` / `mypy strict`
green · bank demo guardrails green · note in your handover that the Postgres hardness
re-verification (fresh output → `dbt build`) is required before release, with the exact
steps from CLAUDE.md's 2026-07-07 paragraph · CLAUDE.md milestone paragraph ·
conventional commits referencing the spec.
