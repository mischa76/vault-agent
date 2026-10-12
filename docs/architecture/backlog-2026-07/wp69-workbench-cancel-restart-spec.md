---
type: spec
status: not-measured
updated: 2026-10-12
---

# WP69 — Workbench backend: cancellation and restart robustness

Status: **Approved and in progress** (2026-10-12, user: „Abbruch und Neustart-Festigkeit im
Workbench-Backend“) · Owner: Mischa Eismann · Author: Claude. Closes the two limits WP66 §5
left open and the user meets when using the workbench: a running run cannot be stopped, and a
finished run's state is gone after a server restart. One small CLI change (an optional
`thread_id` on `_run_pipeline`); no agent, gate or prompt changes; the suite stays keyless.

## 1 Scope

`POST /api/runs/{id}/cancel`, `POST /api/runs/{id}/continue`, a run status `interrupted`, the
final state persisted beside the run's checkpoint, and a startup pass that turns runs the
server died on into `interrupted` runs the CLI and the API can continue or discard. The
frontend gains the two buttons and the status.

## 2 The rules

1. **A cancelled run is an interrupted thread, exactly as a crashed one.** Cancelling the task
   (`asyncio.Task.cancel`) leaves the thread's latest checkpoint in place; the manager writes
   the pending pointer with phase `crashed` (the CLI's own phase for „a thread with work in
   it and nothing running“) and the error `cancelled from the workbench`, and the status
   `interrupted`. From there the CLI's `vault-agent resume --out <run>` continues it
   (`_continue_pipeline`, the latest checkpoint re-executes the node that was running) and
   `--discard` drops it; the API's `continue` and `discard` are those two commands and are
   recorded as such.
2. **The thread is known from the start.** `_run_pipeline` takes an optional `thread_id`
   (default: the uuid it draws today); the manager draws it and writes it into `run.json`
   before the task starts, so a cancel or a server death never loses the pointer to the work.
3. **The final state is persisted.** A run that finishes writes `.vault-agent/state.json`
   (the state's JSON dump, beside the trace — same sensitivity, same gitignore); `state()` reads
   it when the process holds no state, so Model, Artefacts and the console answer after a
   restart. A paused run's state comes from its checkpoint as before.
4. **Startup reconciles.** A `run.json` whose status is `running` when the manager starts
   belongs to a server that is gone: with a thread and a checkpoint database the run becomes
   `interrupted` (pending pointer written, continuable); without, `failed`. One server process
   per root — two on the same root would reconcile each other's runs, and that is documented,
   not guarded.
5. **The single slot stays.** `continue` is a start for the slot's purposes (409 while another
   run is active); `cancel` frees it when the task has ended.

## 3 Guards before the change

1. `_run_pipeline(..., thread_id=X)` uses `X` (the trace file is named after it).
2. A run on slowed stub agents, started without waiting, cancelled while running: status
   `interrupted`, `pending.json` phase `crashed` naming the thread, `cli_equivalents` ends with
   the resume command; `continue?wait=true` ends `paused` on the blocking stub; the checkpoint
   is then decided and the run finishes; a second cancel on a finished run answers 409.
3. A finished run in app A: app B over the same root serves `GET …/model` (hubs present) and
   the console's `status` with kind `answer`; `.vault-agent/state.json` exists.
4. A `run.json` left at `running` with a thread and a checkpoint database: a new manager
   marks it `interrupted` and writes the pending pointer; one without a database: `failed`.
   `discard` on an interrupted run answers 200 and ends `discarded`.

## 4 Pre-registration

Keyless only: the behaviours are the CLI's crash paths, verified on the stub agents; a paid run
would add nothing but a longer window to cancel in. The frontend's buttons are walked once in
Chromium on the stub server (cancel is not reachable there — the stub finishes in seconds —
so the walk checks the interrupted run's Continue/Discard after a reconciled restart instead).

## 5 Not in this WP

Parallel runs; killing a run from the CLI side while the server holds it; reconciling across
two server processes on one root.

## 6 Results

*(appended after the change)*

**2026-10-12 — built, keyless.** Spec and guards `c54fae9` (red), the change `eefc389`, docs in
the commit carrying this line. `cli._run_pipeline(..., thread_id=)`; `RunManager.cancel`,
`continue_`, `_interrupt`, `_reconcile`, the persisted `state.json`; `POST …/cancel` and
`POST …/continue`; the Run tab's Cancel / Continue / Discard. Four guards: the slowed stub
modeler gave a 3 s window, the cancel landed inside it, the pending pointer carried the thread
with phase `crashed`, `continue` ended paused and the checkpoint finished the run; a finished
run served its model and its console from `state.json` in a second app; a `run.json` left at
`running` became `interrupted` with its pointer written, a thread-less one `failed`, and
`discard` ended the interrupted one. The WP68 guard „no state in this session“ was narrowed to
a run whose persisted state is gone — §2.3 changes what it asserted, deliberately. **§4:** the
Chromium walk (`frontend/e2e/interrupted.mjs`): a run paused on the stub server, the server
killed with its `run.json` set back to `running` and the pointer removed, the next server
marked it `interrupted` („the server stopped while the run was running“), the Run tab offered
Continue, the click reached the checkpoint, and `run.json` recorded `vault-agent resume --out
…`. Cancel itself is not reachable in a browser walk on the stub (it finishes in seconds); its
guard is the evidence. **Not measured:** a cancel during a real model call (the SDK call
receives the cancellation; the guard's window is a sleep in the modeler stub).
