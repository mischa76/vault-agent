# Kick-off WP6 — Eval harness

You are a senior ML/data engineer working on **vault-agent** (this repository). Your task
is exactly one work package; build it in the spec's layer order (data → scorers → runner →
LangSmith), one commit per layer.

## Read first, in this order
1. `CLAUDE.md` — repo canon (note: LangSmith is the declared tracing/eval stack).
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp6-eval-harness-spec.md` — your spec.
4. `src/vault_agent/source_schema.py` (the loader-style you must mirror: typed, inert on
   empty, attributable errors), `src/vault_agent/rules/dv2_rules.py`
   (`normalize_identifier`), `src/vault_agent/cli.py` (`_run_pipeline` — the runner reuses
   this entry shape), `docs/demos/` + `examples/inputs/` (dataset sources),
   `src/vault_agent/config.py` (`langsmith_*` settings).

## Preconditions
WP4 (typed `ValidationIssue`) must be merged (the scorers consume it). If not: STOP,
report.

## Task
Implement the spec: dataset format + typed loader (bank, health_insurance,
messy_insurance cases), the four deterministic scorers with pinned-score unit tests, the
live runner (`python -m eval.run`) with repeat/variance reporting and JSON results, the
import-guarded LangSmith upload layer, `eval/README.md`.

## Constraints
- Layers 1+2 fully keyless-tested; layer 3 never runs in the default pytest suite.
- Golden matching is structural via `normalize_identifier` — no string-equality on raw
  labels, no LLM-based scoring.
- You cannot execute layer 3 without an API key: mark the manual verification step
  (§8.2) as an explicit TODO for the human reviewer in your handover notes.

## Definition of Done
Spec §8 acceptance criteria verified (§8.2 as documented manual step) · `uv run pytest -q`
/ `ruff` / `mypy strict` green (mypy also over `eval/` — add it to the checked paths) ·
CLAUDE.md milestone paragraph · conventional commits referencing the spec.
