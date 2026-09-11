---
type: kickoff
status: keyless-only
updated: 2026-09-11
---

# Kick-off WP35 — Databricks as a selectable target platform

You are adding the first non-Postgres target the generator knows by name. Keyless: no workspace
exists on this machine, and the user asked for the code first („erstmal keyless").

## Read first
1. `CLAUDE.md` — the invariants on verifying against the installed thing and writing the guard
   before the change both bind; the guard here already exists (WP7's staging baseline, WP23's
   greenfield manifest) and must stay green untouched.
2. `docs/log.md` 2026-08-24 — why the dbt line stays at 1.9; the Databricks adapter must fit it.
3. `wp35-target-platform-databricks-spec.md` — binding, §2 first.
4. `agents/staging_generator.py` `_SEED_TYPE_BY_JSON_TYPE` … `_render_readme` — the only
   platform-specific output there is.
5. The installed package: `demo/bank_postgres/dbt_packages/automate_dv/macros/tables/databricks/`.

## What to build (spec §3)
1. `rules/platforms.py` — the profiles, the dialect, the import-time consistency check.
2. `VaultAgentState.target_platform`, `--target-platform`, threaded through both
   `build_staging` call sites.
3. Tests in `tests/test_target_platform.py` and the pinned Databricks scaffolding fixture.
4. `demo-databricks` extra, lock resolved.
5. Manual 6.2 (flag), 9.6 (platform notes, keyless wording), 4 (extra); index; log.

## Done when
Spec §5 items 1–6 pass keyless; ruff, bare mypy, full pytest green; the log entry says which
claims are keyless-only — all of them.
