---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP111 — The workbench tested through its API, and a coverage floor for `vault_agent.ui` (C19)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C19 from the maturity analysis of 2026-10-22: WP78's relative-path defect passed every test because
none went through the API; `ui/console.py` 70 %, `ui/app.py` 79 % line coverage (from the analysis).

## 1 Measured before the change

The whole suite (1485 tests) with `--cov=vault_agent.ui`: **82 %** of the package's 998 lines — `app.py` 82 %,
`console.py` 70 % (as the analysis said), `runs.py` 88 %, `projects.py` 91 %, `project_check.py` 92 %, `graphs.py`
100 %. Nine test files use the `TestClient`; the routes they call: project create/list/get, file upload, run start,
checkpoint read and decide, cancel, continue, artefacts list, project check, parse, model, console, the SPA. Never
called through the API: an artefact fetched by path (only the traversal attempt), the report, a paged event read past
the end; and almost every error branch (the 404 of an unknown project or run on each route, the 400 of a bad file
name or suffix, the 409/400 of a decision, cancel or continue in the wrong state, the 422 of a bad as-of grain).
The console's uncovered lines are the branches of `explain`, `why`, `show`, `steering` and the free-text fallbacks.

## 2 The rules

1. **Every action that hands a path on is tested through the API** — the file upload's name (`../`, a directory, an
   empty name, `.`), its suffix, an empty schema (the file removed again), a run's missing input and missing
   predecessor, an artefact fetched by a nested and a top-level path, a missing artefact, the checkpoint directory's
   `state.json` (served by path, unlisted), the report; the parse endpoint's subprocess stays WP78's injected runner
   and the default runner is exercised on a harmless command.
2. **Every error branch answers through the API with the code it has today**, pinned: 404 for an unknown project or
   run on each of the 13 run routes, 400 for a name that is not a plain name and for a wrong suffix, 400 for a
   decision or a continue on a run that is not paused or interrupted, 409 for a cancel of a run that is not running,
   422 for a bad as-of grain. Two behaviours found while pinning and left as they are: a body with `accept` and
   `discard` both true discards (the discard branch comes first); recorded, not changed here.
3. **Every console command answers**, one test per command, on the paused stub run — `help`, `?`, the empty line,
   `status`, `items` and its two filters, `explain` by number, out of range, by gate code, by flag kind, by asset,
   `gate`, `gates`, `flags`, `steering` with and without an id, `cli`, `why` and `show` on an unknown name, `what if`
   accept and discard, and the free-text fallbacks (a construct, a gate code, a flag kind, an asset, gibberish) — and
   changes nothing: the run stays paused.
4. **A coverage floor the CI enforces.** `[tool.coverage.report] fail_under = 85` in `pyproject.toml`; both workflows'
   `uv run pytest` carry `--cov=vault_agent.ui --cov-report=term`, so the floor applies to the package the flag
   measures — the whole suite, measured once, in the run CI already makes; the local `uv run pytest` is unchanged
   (no `--cov`, the same speed). A guard pins the number and both workflow lines, so the floor cannot drift out of CI
   silently. 85 is five points under the first measurement of this WP's own result, rounded down to a multiple of
   five (§6 says what that measurement was).

## 3 Not this WP

Branches a stub cannot reach without a failing or slow agent (the crash path of `_continue`, `_fail`'s crashed/failed
split beyond WP69's, the resolution checkpoint's pending resolutions beyond WP71's); changing any behaviour the pins
found (the accept-and-discard body); a floor for the whole package tree (the suite's overall coverage is not a
product statement; the workbench's is, because its paths reach the disk and a subprocess).

## 4 Acceptance (keyless)

`tests/test_wp111_workbench_api_coverage.py`: the tests of rules 1–3 (green today where they pin, red where they
found a gap in the fixture — none did) and the floor guard (red before the change: no `fail_under`, no `--cov` in CI).

## 5 Pre-registration (keyless)

- **P1** With the new tests the whole suite's coverage of `vault_agent.ui` rises from 82 % to **at least 90 %**;
  `console.py` from 70 % to at least 85 %, `app.py` from 82 % to at least 95 %. Any file that stays under its
  prediction is named with the lines that remain and why a stub cannot reach them.
- **P2** The floor is set at 85 (§2.4), the CI command measures only the package, the guard pins both workflows;
  `uv run pytest` without `--cov` takes the same time as before (within noise).
- **P3** Suite green, ruff, bare mypy; no workbench behaviour changes (the pins are the record of today's codes).

## 6 Measured

Appended after the run.
