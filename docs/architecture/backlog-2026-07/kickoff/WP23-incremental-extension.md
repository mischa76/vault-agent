# Kick-off WP23 — Incremental vault extension, Phase 1 (brownfield mode)

You are a senior data engineer building vault-agent's brownfield mode: extending an
existing, previously generated vault additively — the everyday DV2.0 scenario. Keyless
work throughout (the modeler stays injectable); the Postgres hardness build at the end
is the maintainer's live step. This is an L-sized WP — work through the spec in order,
the inertness guard comes FIRST.

## Read first
1. `CLAUDE.md` (canon: conventions, "What NOT to do", milestone).
2. `docs/architecture/backlog-2026-07/incremental-extension-charter.md` — the accepted
   charter incl. the five §5 decisions (extension run, grandfathering, flagged
   migration, delta-ADR, one queue). The charter's reasoning binds interpretation.
3. `docs/architecture/backlog-2026-07/wp23-incremental-extension-spec.md` — the binding
   spec (§2.1–§2.9).
4. Code you will touch or mirror: `cli.write_outputs` (+ `_safe_component`, WP20),
   `source_schema.py` (house loader style), `state.py`, `agents/dv2_modeler.py`
   (+ WP16 registry in `rules/dv2_rules.py`), `agents/validator.py` (gate patterns),
   `agents/staging_generator.py` + `agents/code_generator.py` (WP10 multi-source paths
   — grandfathering hooks in here), `agents/adr_author.py`, `report.py`,
   `agents/orchestrator.py` (ExecutionPlan).
5. Tests to mirror: `test_staging_regression.py` (byte-identity pattern),
   `test_multi_source_hub.py` (WP10 pins you must not break),
   `test_demo_mapping_postgres.py` (demo guardrail style).

## Order of work (spec §2/§3 — the spec wins on conflict)
1. **Inertness guard first** (spec test #1): pin greenfield byte-identity before any
   change.
2. §2.1 `dv_model.yml` output + `existing_model.py` loader (+ round-trip test #2).
3. §2.2 state/CLI/plan; §2.4 `model_merger.py` (+ `FlagKind.EXTENSION_CONFLICT`).
4. §2.5 the five `E_/W_EXISTING_*` gates.
5. §2.3 modeler extension prompt section — new steering rules go through the WP16
   registry; update the prompt fixture + steering ledger DELIBERATELY in the same
   commit (WP20 precedent) and say so in the commit body.
6. §2.6 grandfathering in staging/codegen — the trickiest part; the WP10 greenfield
   tests and both demos must stay byte-identical.
7. §2.7 diff artifact + report section; §2.8 delta-ADR.
8. `bank_extension` eval case (acceptance #2).

## Verify
- Full spec-§3 test list green; WP10/demo/staging byte-identity guards untouched.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.
- State plainly in the final report which acceptance items remain open (the live
  Postgres on-top build, #3, if you cannot run it).

## Out of scope
Phase 2 entity resolution (spike), foreign-vault introspection, destructive migrations
(flag only), mapper behaviour changes.

## Definition of Done
Spec §4 met with evidence; CLAUDE.md milestone paragraph appended (honest about open
live steps); conventional commits referencing this kick-off, the spec, and the charter.
