# Kick-off WP18 — Eval gate integrity (review finding 2026-07-28 #2)

You are a senior engineer closing the remaining "gate passes on absence of evidence"
holes in the eval harness — the fourth recorded instance of this defect class (after
WP9.2, WP14, and the vacuous-`_f1` fix). **eval/ only — no src/vault_agent change.**
Keyless work.

## Read first
1. `CLAUDE.md` (canon; note the 2026-07-28 "vacuous scorer" milestone paragraph — you are
   generalising exactly that fix).
2. `docs/architecture/backlog-2026-07/wp18-eval-gate-integrity-spec.md` — the binding spec.
3. `eval/run.py` (`failed_gates`, `vacuous_scorers`, `render_table`, `main`),
   `eval/scorers.py` (every mapping-family scorer), `eval/datasets.py` (the loader's
   vacuity rejection — the rule you extend to runtime), `eval/README.md` (scorer
   semantics you will update).
4. `tests/test_eval_run.py`, `tests/test_eval_scorers.py`, `tests/test_mapping_scorers.py`
   — know the existing pins before you change any details string.

## What to build (spec §2, summarised — the spec wins on conflict)
1. A gated scorer absent from `stats` → `GATE UNSATISFIABLE` on stderr, exit 1 (typo'd
   name and missing `golden_mapping.yml` are the two real triggers).
2. One vacuity convention: nothing-to-check → score 1.0 + details starting `"vacuous — "`
   for `mapping_coverage`, `false_friend_hits`, `gap_detection` (prefix order: vacuous
   first, the reported-only note after), `mapping_accuracy`, and `confidence_calibration`
   (polarity fix: 0.0 → 1.0). Do not touch `construct_f1`/`driving_key_accuracy`.
3. Runtime vacuity gate: a gated scorer vacuous in every repeat → `GATE UNSATISFIABLE`,
   exit 1 (the loader cannot see the golden mapping; the runner can).
4. Check `eval.ablate` for pins on the old polarity; update deliberately if any.

## Verify
- Spec §3 tests all green; every deliberately changed pin named in the commit body.
- Manual (not committed): temporarily removing scale_30's `golden_mapping.yml` in a
  scratch copy makes `python -m eval.run --dataset scale_30` exit 1 with
  `GATE UNSATISFIABLE` *before* any LLM call is attempted — if the current code reaches
  the LLM first, note it; do NOT restructure the runner to avoid it (out of scope), the
  gate check after scoring is the contract.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
Name-keyed hub/satellite matching, new scorers, gate-threshold changes, anything under
src/vault_agent/.

## Definition of Done
Spec §4 met with evidence; `eval/README.md` documents the vacuity convention; CLAUDE.md
milestone paragraph appended; conventional commit(s) referencing this kick-off.
