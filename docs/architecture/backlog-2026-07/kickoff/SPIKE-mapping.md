# Kick-off SPIKE — business↔source mapping (Phase 2, ADR-0008)

You are a senior data engineer running a timeboxed DESIGN SPIKE for the vault-agent
project. This is NOT a work package: you produce evidence and a decision memo, not
production code. Requires a live `ANTHROPIC_API_KEY` (in `.env`) — run this locally
(Claude Code / WSL), not in a restricted sandbox.

## Read first, in this order
1. `CLAUDE.md` — repo canon (binding).
2. `docs/architecture/adrs/ADR-0008-source-to-target-mapping.md` — the guardrails. Every
   spike decision must stay inside them; if an experiment suggests amending the ADR,
   that goes into the memo as a recommendation, never as silent deviation.
3. `docs/architecture/backlog-2026-07/spike-mapping-charter.md` — your charter: goal,
   non-goals, deliverables D1–D6, dataset traps, scorer definitions, A/B protocol,
   memo questions, exit criteria. It is the contract for this spike.
4. `eval/README.md`, `eval/datasets/messy_insurance/`, `eval/scorers.py`,
   `eval/run.py` — the WP6 patterns your D1/D2 must follow exactly.
5. `examples/inputs/messy_insurance_source_schema.yml` + requirements doc — the substrate
   you extend (minimally, anonymized) for the §4 traps.
6. `src/vault_agent/llm.py` (`ForcedToolCaller`) — the only LLM call path allowed.

## Order of work (matches the charter)
1. **D1 golden mapping + profiling.yml** — design the traps FIRST; they are the point.
2. **D2 scorers** with pinned-score keyless tests (these are permanent eval code: repo
   conventions, ruff, mypy over `eval/` apply).
3. **D3 prototypes** under `spike/` (throwaway; add `spike/` to .gitignore).
4. **D4 measured runs** — ≥ 5 repeats per variant, record scores/tokens/latency as JSON;
   then the degraded-mode probe and the trap autopsy.
5. **D5 memo** `spike-mapping-results.md` answering charter §7 Q1–Q6, each with the
   evidence line that justifies it. Where evidence is thin, say so.
6. **D6** draft `wp9-mapping-spec.md` in the backlog spec format (problem → target design
   → per-file changes → tests → acceptance criteria) + one-paragraph ADR-0008 status
   recommendation. Mark open decisions FOR THE MAINTAINER (esp. charter Q6 rename-layer)
   as explicit decision points, not as chosen defaults.

## Constraints
- Timebox: 2–3 agent-days of effort. Exit criteria per charter §8 — an honest negative
  result is a valid outcome; do not polish past the timebox.
- No changes under `src/vault_agent/`. Suite/ruff/mypy stay green throughout.
- Sonnet-tier models unless measurements justify otherwise; track cost per run.
- All dataset content anonymized (ATLAS convention, see public-readiness note).

## Definition of Done
D1–D6 delivered (or timebox documented in the memo) · pytest/ruff/mypy green ·
`python -m eval.run --dataset messy_insurance` still works unchanged · memo + WP9 draft
committed; spike/ code removed or ignored · conventional commits referencing the charter.

## Final report
Deliverable inventory with paths, the D4 results table, your answers to charter §7 in one
line each, the ADR-0008 recommendation, and the explicit list of decisions awaiting the
maintainer.
