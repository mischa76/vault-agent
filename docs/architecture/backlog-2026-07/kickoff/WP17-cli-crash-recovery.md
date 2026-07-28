# Kick-off WP17 — CLI crash recovery (review finding 2026-07-28 #1)

You are a senior Python engineer giving the vault-agent CLI the crash-safety its eval
harness already has (WP14.1): no pipeline exception may lose checkpointed, paid-for LLM
work. Keyless work — no API key needed; everything is testable against the stub graph and
a real sqlite saver in tmp.

## Read first
1. `CLAUDE.md` (canon: conventions, "What NOT to do", current milestone).
2. `docs/architecture/backlog-2026-07/wp17-cli-crash-recovery-spec.md` — the binding spec.
3. `src/vault_agent/cli.py` in full — especially `_run_pipeline`, `_resume_pipeline`,
   `_paused_state`, `_write_pending`/`_read_pending`, the WP12 interactive flow, and the
   WP5 §5.5 thread-pruning comments.
4. `tests/test_cli.py` (the stub-graph and pty/TTY test patterns you will extend).
5. The installed langgraph + langgraph-checkpoint-sqlite sources for: resuming a thread by
   invoking with `None` input, and listing thread ids in the sqlite saver. **Verify both
   against the installed packages, not memory** (the WP8 t_link lesson).

## What to build (spec §2, summarised — the spec wins on conflict)
1. `pending.json` gains `phase: "paused" | "crashed"` (+ `error` when crashed); a missing
   `phase` reads as `"paused"` (backward compatible).
2. Crash path in `_run_pipeline`: on any exception write the crashed pending, best-effort
   recover the last checkpoint state (`aget_state` — extract a shared helper from
   `_paused_state`) and `write_outputs` it, then RE-RAISE. Recovery failures must never
   mask the original exception. Do not delete the thread.
3. `resume` on a crashed pending: continue via `ainvoke(None, config)` on the same thread;
   on completion, today's finalize; on a HITL interrupt, apply given decision flags via
   the existing `Command(resume=...)` path, else interactive/print (capability parity).
   New `resume --discard`: delete thread + pending, print what was discarded.
4. Orphan pruning at `run` start: delete threads `pending.json` does not reference;
   listing failure → skip pruning, never block the run. Document the single-slot-pending
   semantics in the help text.

## Verify
- All seven test scenarios in spec §3 (crash persists + artifacts-so-far; resume
  continues cross-connection; crashed→interrupt both branches; `--discard`; recovery
  never masks; orphan pruning spares the pending thread; pause-path regression incl. a
  phase-less legacy pending).
- The non-TTY byte-identity guard for today's pause output stays green apart from the
  documented additions.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` (strict, canonical
  invocation) all green.

## Out of scope
Retry-with-different-parameters, partial agent re-runs, concurrent runs into one out dir,
UI. WP21 will touch `resume` again (`--no-write`) — do not pre-build it.

## Definition of Done
Spec §4 acceptance criteria met with evidence in the final report; CLAUDE.md milestone
paragraph appended (dated, honest about what is and is not covered); conventional
commit(s) referencing this kick-off and the spec.
