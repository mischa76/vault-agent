# Kick-off WP20 — Construct-name gate + filesystem hardening (review findings 2026-07-28 #4/#5)

You are a senior engineer closing the trust gap between report.py ("every state string is
hostile") and the write path (LLM-derived names straight into file paths and dbt model
names), plus one validator normalisation inconsistency. Keyless work.

## Read first
1. `CLAUDE.md` (canon — especially "Never silently guess": the write guard REFUSES, it
   never renames).
2. `docs/architecture/backlog-2026-07/wp20-name-gates-spec.md` — the binding spec.
3. `src/vault_agent/rules/dv2_rules.py` (`normalize_identifier`, the `SteeringRule`
   registry + WP16 seam), `agents/validator.py` (gate patterns, `E_SAT_DUP_ATTR` vs
   `E_SAT_ATTR_OVERLAP`), `cli.py` `write_outputs`, `agents/staging_generator.py`
   `_staging_name` vs `agents/code_generator.py` `_sat_staging_model` (the two naming
   paths you unify).
4. `tests/test_steering.py` + `tests/fixtures/steering/modeler_rules_pre_wp16.txt` — the
   prompt pin you will update DELIBERATELY (spec §2.2 explains why that is allowed here),
   and `docs/architecture/steering-ledger.md` (the row you add).
5. `tests/test_agents/test_staging_regression.py` + the bank demo guardrails — the
   byte-identity you must not break.

## What to build (spec §2, summarised — the spec wins on conflict)
1. `CONSTRUCT_NAME_PATTERN` + helper in rules/; validator gate `E_BAD_NAME` (error) on
   every construct name; confirm all shipped fixtures comply.
2. `SteeringRule` `construct_naming` (backstop=None, origin cites this review + the
   gate); update the prompt fixture and the steering ledger in the same commit, and say
   so in the commit body.
3. `write_outputs` guard: filename components from state (models, staging, contracts,
   ADRs) with a path separator / `..` / control chars → attributable `ValueError`. Refuse,
   never rename.
4. Unify staging naming on `normalize_identifier(base).lower()` — byte-identical for
   well-formed names, pinned by the existing regression fixture.
5. `E_SAT_ATTR_OVERLAP` keys on normalised attributes, reports original labels.

## Verify
- Spec §3 tests all green; ungrounded staging baseline + bank demo guardrails untouched.
- `rg 'source="data_contract"' src` unaffected (that is WP21's finding — leave it).
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
Renaming existing outputs, Unicode beyond `normalize_identifier`, validator-docstring
count drift (WP21), any change to what the modeler prompt says beyond the one new rule.

## Definition of Done
Spec §4 met with evidence; CLAUDE.md milestone paragraph appended (note the deliberate
prompt change explicitly); conventional commit(s) referencing this kick-off and the spec.
