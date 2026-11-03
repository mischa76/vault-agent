---
type: spec
status: not-measured
updated: 2026-11-03
---

# WP118 — The workbench's ids are checked before any path; the owner spec parses in linear time (C43)

Status: **Approved and in progress** (2026-11-03, on the owner's go after the alerts were read on 2026-11-01) ·
Owner: Mischa Eismann · Author: Claude. C43 in candidates part 3; the 97 open CodeQL alerts of 2026-11-01.

## 1 What is wrong

`ProjectStore._dir(project_id)` is `root / project_id` with one check: a `project.json` lies there. A run's stamp
is used the same way (`run_dir`, `delete_run_dir`, `RunManager._meta_path`). Both arrive from a URL segment. A
browser normalises `..` away, but a client that sends `%2E%2E` does not: measured on 2026-11-03 with the test
client, `GET /api/projects/%2E%2E` reaches `get_project` with `project_id == ".."`, and `GET /api/runs/p:../x`
reaches with `run_id == "p:.."`. With a `project.json` in the root's parent — the shipped demo's root is a
sub-folder of a tree the owner names — `..` is a project: readable, its settings writable, and `DELETE` removes
the parent whole (`shutil.rmtree(self.root / project_id)`). The exposure is small (loopback bind since WP92, one
user per ADR-0015, cross-origin writes preflighted and refused), the fix smaller.

`cli._parse_owner` matches a bare address with `[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+` and the bracketed one with
`re.search(r"<([^>]+)>", rest)`. Both backtrack quadratically: measured 2026-11-03, 60 000 characters cost
7.0 s (`<` repeated) and 11.3 s (`a@` plus dots plus a space). The spec comes from the command line or the
workbench's checkpoint form — the same single user — but CodeQL is right that the pattern is the wrong tool.

## 2 The rules

1. **An id is checked before a path is built.** A project id must match what `_slug` produces, `[a-z0-9-]+`;
   a run stamp what `RunManager.start` stamps, `%Y%m%dT%H%M%S%fZ`, so `\d{8}T\d{12}Z` (the candidate note said
   15 digits — the code decides, and the shipped demo's runs are `20261022T233041709632Z`). The check lives in
   the store (`_dir`, `run_dir`, `_run_metas`); every reader of an id goes through one of them, and
   `delete_run_dir` goes through `run_dir`. A failing id is `ProjectError("no project …")` /
   `ProjectError("no run …")` — the 404 the API already answers for a missing one, so an attacker learns no
   more from a malformed id than from a wrong one.
2. **The owner spec parses without a regex.** The bare address: `partition("@")`, no whitespace, `<`, `>` or
   `@` in either part, a `.` in the domain with characters on both sides — exactly the old pattern's language.
   The bracketed e-mail: the first `<` that is followed by at least one non-`>` character and then a `>`, found
   with `str.find` in one pass — exactly what `re.search` returned. Linear in the length of the spec.

## 3 Guards (committed red first)

`tests/test_wp118_untrusted_ids.py`: `..` as a project id with a planted parent `project.json` is `ProjectError`
at the store and 404 at the API (`%2E%2E`), the parent untouched after a `DELETE`; `..` as a run stamp is
`ProjectError` at the store and 404 at the API; every id the store creates passes its own check (the shipped
demo's runs included); the owner parser agrees with the old regexes on a table of specs and finishes a
60 000-character spec under two seconds (the old code: 7 and 11 seconds on this machine).

## 4 Not in scope

The CLI's, `existing_model.py`'s, `trace.py`'s, `profiling.py`'s and `source_schema.py`'s path alerts: paths the
owner types for the owner's own files, in the single-user tool of ADR-0015; they are dismissed with that reason
in the triage pass, not changed. The static route's `..` check (`app.py`) and the artefact route's resolve-and-
parents check (`runs.artefact`) are already right and stay.

## 5 Measurement

Keyless only: the suite with the guards; no live run touches this. After the push, CodeQL's next run decides which
of the 46 workbench alerts close as fixed and which stay because the scanner does not read a `fullmatch` as a
barrier — those are dismissed as false positives naming the check. The log entry records both counts.
