# WP17 — CLI crash recovery

Status: Proposed · Size: M · Depends on: — · Source: project review 2026-07-28, finding 1

## 1. Problem

A pipeline run that raises after expensive LLM work loses everything the user paid for.
When any node raises (a truncation past `MAX_SPLIT_DEPTH`, a non-retryable 4xx such as an
exhausted credit balance, an unreadable document — review finding 6), `_run_pipeline`
propagates (`cli.py:711-718`), `write_outputs` never runs, no `pending.json` is written,
and `resume` refuses (`cli.py:777-780`: it requires `pending.json`). The state IS in
`checkpoints.sqlite` — every completed node checkpointed under the run's thread — but no
CLI surface can reach it: the thread_id is printed nowhere.

Secondary defect: the orphaned thread is never pruned. WP5 §5.5 deletes only *finalised*
threads, so crashed runs regrow `checkpoints.sqlite` unboundedly — the exact failure WP5
fixed, reintroduced through the crash path.

The eval harness got crash-safe persistence in WP14.1; this WP is the CLI's parity half.

## 2. Target design [ENFORCE]

### 2.1 `pending.json` gains a phase

Extend the pending file (shape stays `dict[str, str]`, backward-compatible):

```json
{"thread_id": "...", "input": "...", "phase": "paused" | "crashed", "error": "<summary>"}
```

- The HITL-interrupt path writes `phase: "paused"` (today's semantics; `error` absent).
- A missing `phase` key reads as `"paused"` (files written before this WP keep working).

### 2.2 Crash path in `_run_pipeline`

Wrap the `ainvoke` inside the existing `async with saver` block:

1. On any exception: write `pending.json` with `phase: "crashed"`, the thread_id, the
   input path, and `error = f"{type(exc).__name__}: {exc}"`.
2. **Best-effort artifacts-so-far:** load the last checkpoint via `compiled.aget_state
   (config)` (the `_paused_state` mechanics — extract a shared helper rather than
   duplicating), validate into `VaultAgentState`, and call `write_outputs`. Guard the
   whole recovery in its own try/except: recovery must NEVER mask or replace the original
   exception — on a recovery failure, log it and re-raise the original.
3. Re-raise. The `run` command's except-branch then prints, in addition to today's
   one-liner: that partial artifacts (if any) are under `<out>/`, and the resume command.

Do NOT delete the thread on the crash path — it is exactly what resume continues.

### 2.3 `resume` continues a crashed thread

On `phase == "crashed"`, `resume` continues the thread by re-invoking the compiled graph
with `None` as input on the same thread_id (LangGraph resumes from the latest checkpoint
and re-executes the failed node — **verify this against the installed langgraph version,
not from memory**; the WP8 t_link lesson applies to framework behaviour too). Then:

- Run completes → today's finalize path (write, prune thread, clear pending).
- Run reaches the HITL interrupt → exactly the `run` command's pause handling: if decision
  flags (`--owner`/`--accept`/`--mappings`/`--map`) were given, apply them immediately via
  the existing `Command(resume=decision)` second invoke; else interactive prompt / print
  instructions (capability parity, WP12 rule).
- Run crashes again → the crash path above runs again (pending stays `crashed` with the
  new error). Deterministic failures (e.g. a corrupt PDF) will loop only as often as the
  human retries — acceptable; the error summary names the cause.

New flag `resume --discard`: delete the pending thread (`adelete_thread`) + `pending.json`
+ print what was discarded. The escape hatch for a run not worth continuing.

### 2.4 Orphan pruning at `run` start

`pending.json` is single-slot per output directory (already true today — document it in
the `run`/`resume` help text). At `_run_pipeline` start, delete any thread in the
checkpoint DB that `pending.json` does not reference (SQLite: list distinct thread_ids;
verify the API against the installed langgraph-checkpoint-sqlite). This catches
SIGKILL-class crashes that never reached the except-branch. Skip pruning entirely when
listing fails — pruning is hygiene, never a reason a run can't start.

## 3. Tests (keyless, stub-graph pattern from `tests/test_cli.py`)

1. A node that raises mid-pipeline → `pending.json` has `phase: "crashed"` + error;
   artifacts-so-far written (models from the checkpointed state present); original
   exception surfaces; thread still in the DB.
2. `resume` on the crashed pending continues from the checkpoint (real
   `AsyncSqliteSaver` in tmp, cross-connection — the existing precedent), finalises,
   prunes, clears pending.
3. Crashed run that pauses at HITL after continuation → decision flags applied /
   instructions printed (both branches).
4. `resume --discard` removes thread + pending.
5. Recovery-failure guard: `aget_state` raising inside the crash path does not mask the
   original exception.
6. Orphan pruning: a stray thread not referenced by pending is gone after the next `run`;
   the pending thread survives.
7. Regression: pause path byte-identical apart from the added `phase` key; a pre-WP17
   `pending.json` without `phase` resumes as paused.

## 4. Acceptance criteria

1. No pipeline exception can lose checkpointed work: after any mid-run crash, `resume`
   (or `resume --discard`) has a defined, tested behaviour.
2. `checkpoints.sqlite` cannot grow unboundedly through crashed runs (except- and
   SIGKILL-path both covered).
3. Recovery never masks the original error; `--debug` still yields the full traceback.
4. Standard DoD (00-overview §Shared conventions).

## 5. Out of scope

Retrying the failed node with different parameters, partial re-runs of individual agents,
and any UI surface. Concurrent runs into one output directory stay unsupported
(single-slot pending, now documented).
