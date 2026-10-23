---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP78 — The workbench says whether a run's project resolves and parses: the deterministic resolution check always, `dbt parse` when dbt is installed, no warehouse

Status: **Approved and in progress** (2026-10-17, the owner's go for stage 1 as WP78) · Owner:
Mischa Eismann · Author: Claude. From the question of 2026-10-17 whether the build is shown in
the UI: it is not — the workbench ends where the pipeline ends, at the written dbt project, and
the only evidence of buildability a reviewer sees is the `source_binding` flags. Stage 2 (a
`dbt build` against a configured profile with its log) is deliberately not built: the build
belongs to the customer's CI, not to the modelling workbench (14.3).

## 1 What is missing, in one paragraph

Twenty chains were judged green without anyone parsing their projects; WP74 added
`unresolved_stage_refs` and the `project_self_contained` scorer to the *eval harness*, WP76 made
the projects parse, WP77 made them keep their bindings — and none of that is visible where a
human looks at a run. A reviewer at the sign-off should see, for this run, whether every stage
reads a relation dbt can resolve, which stages a human must still provide, and — when dbt is in
the environment — whether `dbt parse` accepts the project as written.

## 2 The rules

1. **The resolution check is deterministic and always on.** `GET /api/runs/{id}/project` reads
   the written project (`models/staging/*.sql`, `models/staging/sources.yml`,
   `metadata/automatedv.yml`) and answers: the number of staging models, the stages
   `unresolved_stage_refs` names (dbt could not resolve them), the stages whose binding is
   inferred (`source_binding: inferred` in the staging metadata — what a human must provide),
   whether dbt is available (`dbt-core` version and the installed adapter, `postgres` or
   `databricks`, `null` otherwise), and the last parse result, if any. No model call, nothing
   changed, no warehouse.
2. **`dbt parse` on request, keyless.** `POST /api/runs/{id}/parse` runs `dbt deps` (when
   `dbt_packages/` is absent) and `dbt parse` in the run's output directory, with a throwaway
   `profiles.yml` for the installed adapter whose connection values are placeholders — `dbt
   parse` opens no connection. The result is typed: `status` `ok` | `failed` | `unavailable`
   (no dbt or no adapter in the process), `adapter`, `seconds`, `errors` (the lines dbt marks as
   errors, at most twenty), `log` path; it is persisted in `run.json` under `parse`, and the
   command is appended to the run's `cli_equivalents` — every action taken here is replayable.
   The subprocess runner is injectable, so the suite tests the path keylessly and without dbt.
3. **Shown on the Run perspective** as a section „Project“: staging models, „resolves“
   (unresolved count, red when > 0 with the names), „to provide“ (inferred count with the
   names), dbt availability, a „dbt parse“ button with the last result (status, duration, the
   error lines). The console gains nothing; chapter 14 gains 14.7.
4. **Not a gate.** Nothing here blocks a decision or changes a run; the scorer in the harness
   stays the gate. The workbench reports; the human decides.

## 3 Guards before the change

1. `project_check(out_dir)` on a project written by `build_staging` (WP76 fixture: one inferred
   link stage under the `inferred` block): `staging_models` 3, `unresolved` empty, `inferred`
   `["stg_account_customer"]`; on a project with a bare `raw_` ref: that stage in `unresolved`.
2. `dbt_parse(out_dir, runner=fake)`: with an adapter reported available, the fake runner sees
   `dbt deps` then `dbt parse --profiles-dir …`, a return code 0 gives `status: ok`; a return
   code 2 with „Compilation Error … depends on a node named 'raw_x' which was not found“ gives
   `status: failed` with that line in `errors`; with no adapter available `status: unavailable`
   and the runner is never called; the profile written names the adapter's `type`.
3. The API: after a finished stub run, `GET …/project` answers with the counts;
   `POST …/parse` (runner monkeypatched) stores the result in `run.json`, the next `GET` carries
   it, and `cli_equivalents` gained a `dbt parse` line.
4. The frontend: the Run perspective renders the section from a `ProjectCheck` with one
   unresolved stage (red) and the parse button; the button calls `onParse`.

## 4 Pre-registration

On the twentieth chain's kept fifth project opened as a workbench run (the kept output as
`out_dir`): `staging_models` 145, `unresolved` 0, `inferred` 10 — the ten the build failed on —
and, in the main environment (dbt-core 1.9 with dbt-postgres), `dbt parse` `ok`.

## 5 Not in this WP

Stage 2 (`dbt build` with a profile and a build log in the UI); a parse for a run that is still
running or paused before generation (the project does not exist yet — the section says so).

## 6 Results

*(appended after the change)*
