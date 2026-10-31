---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP112 — Deleting in the workbench: input files, runs, projects (C2)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C2 recorded 2026-10-21 during the owner's hands-on run: the API creates and reads, nothing deletes.

## 1 What is missing

No `DELETE` route (verified again 2026-10-31: `app.py` has 19 routes, none deletes); an input uploaded by mistake, a
run that failed or was discarded, a project that served its purpose stay on disk and in every list until someone
removes the folder by hand — outside the API, with no rule protecting what another run depends on.

## 2 The rules

1. **Three routes, three answers.** `DELETE /api/projects/{id}/files/{name}` removes an input file;
   `DELETE /api/runs/{id}` removes a run's folder whole (its outputs, its checkpoint, its trace);
   `DELETE /api/projects/{id}` removes the project folder with its inputs and runs. Each answers `{"deleted": …}` with
   what went (the project: how many runs and files with it); 404 for what is not there; the file name must be a plain
   name, as on upload.
2. **What is kept, and why — each a 409 that names the reason.** A file a run has read (`run.json` names it as
   `requirements`, `schema` or `profiling`) is kept: the run's CLI equivalent and its record point at it. A run another
   run extends (`existing_run`) is kept while referenced — its `metadata/` holds the model, the catalogue and the
   bindings the extension started from — in this project or any other (run ids carry their project). A running run is
   cancelled first and a paused run decided or discarded first (WP69, WP66): deleting is for runs at rest (`finished`,
   `failed`, `crashed`, `interrupted`, `discarded`). A project is deleted only when none of its runs is running or
   paused and no run of another project extends one of its runs; its own runs' references among themselves go with it.
3. **The server forgets what it deletes.** The run manager drops the run's task handle, its in-memory state and its
   `active` mark; a console question about a deleted run is a 404, not a stale answer. The store does the file work
   (`shutil.rmtree` on the folder the store locates — never a recorded path, WP92).
4. **The frontend asks first.** A `delete` button per input file and per run at rest (disabled while running or
   paused), and one for the project; each confirms (`window.confirm`) before calling the API, shows the API's 409
   detail where a rule refuses, refreshes the project after a file or run, and leaves to the project list after the
   project. The deletion's record is the API's answer and the refreshed lists; the per-run event stream dies with its
   run, and a project has no stream of its own (the candidate's „line in the event stream" reads as this).

## 3 Not this WP

Undo; a recycle bin; deleting from the CLI (`vault-agent` has no store); bulk deletion; deleting a file a run has
read by rewriting the run's record (the record stays true).

## 4 Acceptance (keyless)

`tests/test_wp112_workbench_delete.py`, committed red (seven of seven: no route): an unused input deleted from disk and
list, a read one kept with the run named, 404 and a traversal name refused; a finished run deleted whole and
forgotten (folder, `GET`, console, the project's list, nothing else touched), a paused run refused until discarded, a
running run (WP69's slow stub) refused until cancelled, a base run kept while its extension exists; a project refused
while a run is paused, deleted whole afterwards with the other project untouched, kept while another project's run
extends one of its runs. `frontend/src/Project.test.tsx` (two tests, red): a file deleted after confirmation and not
without it; a finished run's button live, a paused run's disabled, the project deleted after confirmation with the
callback.

## 5 Pre-registration (keyless)

- **P1** The seven API guards green; the deleted folders gone and every other path under the store byte-identical
  (the tree comparison in the run test).
- **P2** `npm run check` and `npm test` green with the two new tests (the suite had 29 frontend tests).
- **P3** Suite green, ruff, bare mypy; the `vault_agent.ui` coverage stays at or above 94 % with the new code covered
  by the new tests; the manual's API table gains the three rows.

## 6 Measured

Appended after the run.
