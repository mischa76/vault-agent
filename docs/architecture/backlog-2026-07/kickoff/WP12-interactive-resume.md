# Kick-off WP12 — Interactive checkpoint prompt (stage 1.5)

You are a senior Python engineer working on **vault-agent** (this repository). Your task
is exactly one work package: the HITL checkpoint becomes answerable directly in the
terminal. One commit (or a small series). Recommended after WP11 (shared CLI summary
lines — trivial, but merge serially).

## Read first, in this order
1. `CLAUDE.md` — repo canon; especially the ADR-0006 paragraphs (checkpoint semantics,
   interrupt/resume, "everything before interrupt() stays pure/idempotent").
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD, and
   the 2026-07-18 addendum (CLI-first invariant).
3. `docs/architecture/backlog-2026-07/wp12-interactive-resume-spec.md` — your spec; the
   §1 capability-parity rule is the design law: the prompt may only offer what the
   `resume` flags offer, and everything runs through the existing parse/build/resume
   functions.
4. `src/vault_agent/cli.py` — read it fully: `run`/`resume`, `_run_pipeline`/
   `_resume_pipeline`, `_parse_owner`/`_parse_map`/`_build_decision`,
   `_mappings_from_file`/`_mapping_sources_from_file`, `_print_checkpoint`,
   `_report_paused`, `_write_pending`/`_read_pending`/`_clear_pending`.
5. `src/vault_agent/agents/orchestrator.py` — `apply_human_decision` (read-only: you
   must NOT change decision semantics), `assemble_review_queue`,
   `HumanReviewQueue.requires_signoff`; `src/vault_agent/models/contract.py` —
   `ContractOwner.PLACEHOLDER_NAME` (owner items are matched on this, never on text).
6. Existing CLI tests (`tests/test_cli.py`) — the paused-path assertions you must keep
   byte-identical, and the invocation patterns for keyless graph runs.

## Task
`--interactive/--no-interactive` (default auto = both stdin and stdout are TTYs) on
`run` and on flag-less `resume`; prompt loop per spec §2 (owners → unresolved mappings →
accept), assembled via `_build_decision`, resumed in-process via `_resume_pipeline`;
injectable prompt seam + `_is_interactive` helper per spec §3.

## Constraints
- `cli.py` + tests only. `apply_human_decision`, graph, state: untouched.
- Non-TTY behaviour byte-identical to today (pin it first, before adding the prompt).
- Abort (skip-all / decline / Ctrl-C) must never lose the checkpoint — `pending.json`
  and the checkpointer thread survive, flag-based `resume` still works afterwards.
- Multi-source (`sources:`) resolution is NOT promptable — list it with the file-based
  pointer (parity rule).
- No new dependency (rich is already present via the existing Console usage).

## Definition of Done
Spec acceptance criteria 1–4 verified (1 needs a real terminal — note the manual smoke
test in your handover if your environment has no TTY) · all new tests keyless and
TTY-free (injected prompts) · `uv run pytest -q` / `ruff` / `uv run mypy src/vault_agent`
strict green · bank demo guardrails green · CLAUDE.md milestone paragraph · conventional
commits referencing the spec.
