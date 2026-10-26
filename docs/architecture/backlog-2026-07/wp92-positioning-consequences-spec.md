---
type: spec
status: not-measured
updated: 2026-10-26
---

# WP92 — ADR-0015's consequences: a project root that moves, the local-only binding pinned, a handover chapter (C20, C24)

Status: **Approved and in progress** (2026-10-26, the owner's choice of Option C on ADR-0015 and his go to
„proceed as recommended") · Owner: Mischa Eismann · Author: Claude. Backlog C20 (`backlog-2026-10-candidates-2.md`),
C24 (relocatable runs, recorded in `docs/log.md` 2026-10-22, never specified). Release criterion 4
(`release-1.0-criteria.md`): „ADR-0015 decided and its consequences done — … either way recorded and built, not
assumed".

## 1 What is wrong, in one paragraph

ADR-0015 was a draft; today it is accepted (Option C: the consultant's single-user tool now, a team tool as its own
ADR when a customer asks). The ADR names what Option A requires — „hygiene, not architecture": relocatable runs, a
documented handover of a project folder, the residency route per engagement, the local-only binding kept as a
security property. Of these, only the residency route exists. A project root cannot move: `run.json` stores `out_dir`
as the path the workbench resolved at start (`runs.py`, `RunManager.read`/`out_dir`, `_reconcile`, the `existing_run`
lookup), relative when `--root` was relative — so the shipped demo works only from the repository root, and a root
copied to another machine, or started from another directory, lists runs whose checkpoints, artefacts and reports
cannot be found. The binding to `127.0.0.1` is a literal in `cli.ui` with no test, so the next `--host` option would
remove the security property silently. No chapter of the operations manual says what a consultant hands over at the
end of an engagement and what stays behind.

## 2 The rules

1. **The store locates a run; `run.json` only describes it.** A run's folder is `ProjectStore.run_dir(project,
   stamp)` under the root the workbench was started with — never the `out_dir` string the file carries. `read()`
   reports `out_dir` as the store resolves it now, so the API and the frontend always show the true location; the
   file keeps what was written at start, as a record. `_reconcile` works on the file's own folder. The `existing_run`
   of a brownfield start resolves the same way.
2. **A root moves whole.** Copying or moving `<root>` to another path or another machine, and starting the workbench
   with the new `--root` from any working directory, lists the same runs with the same statuses; a paused run's
   checkpoint can be read and decided, a finished run's artefacts, project and report can be read. Nothing inside a
   run folder is rewritten for that.
3. **The workbench listens on `127.0.0.1` only.** `vault-agent ui` passes that literal to uvicorn and has no option
   that changes it; a test pins both. Making it reachable from elsewhere is ADR-0015's Option B and needs that ADR.
4. **A handover chapter.** `docs/operations/15-handover.md`: what an engagement's project root holds, what is handed
   to the customer (the generated dbt project with its catalogue, the contracts, the review queue, the ADR, the
   report), what stays with the consultant (traces, checkpoints, the key in `.env`), how the root moves (rule 2), the
   residency route chosen per engagement (5.5), and that the checkpoint's owner is a name typed, not an identity
   (ADR-0015, neutral consequence). Linked from the manual's contents and `docs/index.md`.

## 3 Not this WP

Authentication, users, a shared checkpointer, concurrent runs (ADR-0015 Option B — its own ADR when a customer
asks). Rewriting the `cli_equivalents` inside a moved run (they are a record of what was run, with the paths of that
time). The paths inside `pending.json` and the traces (informational; resume takes `--out`).

## 4 Pre-registration

- **P1** (rule 1, 2 — keyless): a run paused at the checkpoint under root A; A moved to B; a new app over B lists the
  run as paused, serves its checkpoint, takes the decision and finishes it; its artefacts and `run.json` are read under
  B. Red before the change (the checkpoint database is looked for under A).
- **P2** (rule 2 — keyless): a root created relative to one working directory, the app restarted from another with
  the absolute root — the run's `out_dir` as reported is under the root, and its artefacts list. Red before the
  change (a relative `out_dir` resolved against the new directory).
- **P3** (rule 2 — the shipped demo as evidence): `demo/workbench-adventureworks` opened from a working directory
  that is not the repository root lists its runs with their artefacts and reports. Red before the change.
- **P4** (rule 3): `vault-agent ui` calls uvicorn with `host="127.0.0.1"`; `--host` is not an option. A pin, green
  before the change by construction — recorded as such.
- **P5** (rule 4): the chapter exists, is in the contents table and the index — by reading.

## 5 Guards

`tests/test_wp92_relocatable_root.py` (P1–P4). Committed red (P1–P3) before the change.
