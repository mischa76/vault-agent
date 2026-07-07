# Kick-off WP4 — Typed ValidationIssue

You are a senior Python engineer working on **vault-agent** (this repository). Your task is
exactly one work package; do not expand scope.

## Read first, in this order
1. `CLAUDE.md` — repo canon: conventions, "What NOT to do", current milestone. It overrides
   any habit you bring along.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp4-typed-validation-issue-spec.md` — your spec.
4. The code you will touch: `src/vault_agent/state.py`,
   `src/vault_agent/agents/validator.py`, `src/vault_agent/agents/orchestrator.py`
   (`assemble_review_queue`), `src/vault_agent/agents/dv2_modeler.py` (`run`).

## Task
Implement the spec: introduce `ValidationIssue` (pydantic) and migrate every producer,
consumer, and test off issue dicts. No behaviour change: same codes, same severities, same
messages, byte-identical rendered review queue for existing fixtures.

## Constraints
- mypy strict, ruff clean; type hints everywhere; no `dict[str, Any]` issues left.
- Do not touch `state.decisions` (explicitly out of scope).
- Mechanical test migration — never weaken an assertion.

## Definition of Done
`uv run pytest -q` green · `uv run ruff check .` clean · `uv run mypy src/vault_agent`
clean · acceptance criteria §5 of the spec all verified (including the `rg` check) ·
CLAUDE.md milestone paragraph added · conventional commit referencing the spec.
