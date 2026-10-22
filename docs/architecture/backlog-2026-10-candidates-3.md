---
type: backlog
status: proposed
updated: 2026-10-23
---

# Backlog candidates of October 2026, part 3 — recorded so far only in the log

Status: **Proposed, not prioritised** (2026-10-23) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates-2.md` (C8–C21, append-only). C22–C24 were first written into
`docs/log.md` on 2026-10-22 and were findable nowhere else; C25 is the open half of C12. „C" stands for
*candidate*: a finding or idea, not yet a work package; a candidate the owner approves gets a WP number, a
spec with pre-registration and guards first. Status of the earlier candidates: C11 → WP84, C12 → WP83
(phase 1), C13 → WP85, C14–C16 done without a WP, C4 reserved as WP82.

## C22 — PIT and bridge generation

**Correction recorded with it:** part 2 listed PIT/Bridge under „not taken up" with ADR-0007 as the reason —
wrong. ADR-0007's layer table puts „Business Vault — PIT / Bridge" on the **Generate** side and names
„PIT/Bridge generation" as a step of its roadmap gradient (log, 2026-10-22, „Correction: ADR-0007 …").
AutomateDV 0.11.4 ships `pit` and `bridge` for all five platforms with incremental materialisations (read in the
installed package). vault-agent generates neither. Shape of a WP: an as-of-dates model (a date spine;
`dbt_utils` is a dependency already), a PIT per hub with two or more satellites — deterministic from the
model — and bridges along link paths, which need a path choice from the requirements, ratified by a human.
Before specifying: AutomateDV's ghost-record handling for PIT lookups; a PIT over a non-idempotent satellite
picks an arbitrary row, which WP84/WP85 have now closed for the known classes. Next on ADR-0007's roadmap.

## C23 — An AdventureWorks data loader in the repository

The demo `demo/workbench-adventureworks/` and every chain build need Microsoft's AdventureWorks CSVs (MIT)
loaded into the warehouse under the schemas the generated `sources.yml` names, with `load_datetime` and
`record_source` added; the loader so far was a session script (`pg_load_all.py`, log 2026-10-18), not in the
repo, with special cases (`ProductReview`'s multi-line records, `Document`'s CRLF, the hierarchy root's empty
key). Candidate: a loader under `eval/adventureworks/` that downloads the CSVs, applies the DDL's column order
and types, and loads PostgreSQL (Databricks as a second target), so anyone can build the demo, not only browse it.

## C24 — Relocatable runs

`run.json` stores `out_dir` relative to the directory the workbench was started in (`runs.py`:
`Path(meta["out_dir"])`), and a brownfield run names its predecessor the same way. A project root therefore
cannot be moved or copied; the demo works only started from the repository root with exactly
`--root demo/workbench-adventureworks`. Candidate: resolve a run's folder from the store
(`ProjectStore.run_dir(project, stamp)`) and keep `out_dir` for display and CLI equivalents only.

## C25 — Zero-key rows in the hubs (C12, phase 2)

Since WP83 a link row with a missing optional participant carries the zero key `hash('-2')` — but no hub row
carries that key, so a join from such a link to its hub must be an outer join and referential tests would fail.
DV2.0 puts `-1` (required, missing) and `-2` (optional, not applicable) records into every hub. AutomateDV has
ghost records for satellites only. Candidate: a small generated zero-key model per hub, typed like the hub's key,
added to the hub's `source_model` list — or a documented post-hook; the hub-key type is the open design question
(the contracts carry declared types; the warehouse's may differ).
