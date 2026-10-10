---
type: spec
status: not-measured
updated: 2026-10-11
---

# WP66 — Workbench backend: the pipeline as a local API over the CLI's internals

Status: **Approved and in progress** (2026-10-11, ADR-0014 accepted; WP65 phase 1) · Owner:
Mischa Eismann · Author: Claude. New package `vault_agent.ui` (FastAPI, extra `ui`), a CLI
command `vault-agent ui`. No change to any agent, gate or prompt; the suite stays keyless.

## 1 Scope

The API the workbench (WP65) needs, wrapping — never re-implementing — the CLI's internals:
`_run_pipeline`, `_resume_pipeline`, `_discard_pending`, `_build_decision`, `_paused_state`,
`write_outputs`, `_write_pending`/`_read_pending`, the trace writer, `build_report`,
`build_model_mermaid`, `assemble_review_queue`. One process, bound to `127.0.0.1`; one active
run per process (the checkpointer and `pending.json` are single-slot per directory; a second
start answers 409).

## 2 The rules

1. **Projects are folders.** `<root>/<id>/project.json`, `inputs/` (requirements, schema,
   optional profiling), `runs/<run_id>/` as the run's output directory (`vault-agent run --out`).
   A schema file is validated on upload with `load_source_schemas` — a malformed file is
   refused with the loader's message, before any run.
2. **A run is a background task** over `cli._run_pipeline` (greenfield) or with
   `existing_model` from an earlier run of the project (brownfield); afterwards
   `write_outputs`; a pause writes `pending.json` exactly as the CLI does. `run.json` holds
   `status` (`running | paused | finished | failed | crashed`), `thread_id`, the input names and
   **the CLI equivalent of every action taken through the API** (`cli_equivalents`), so a run
   driven from the workbench is replayable from the terminal. `?wait=true` on a start or a
   decision awaits the task (scripts, tests).
3. **The checkpoint is read, not re-decided.** `GET …/checkpoint` returns the review queue
   (`assemble_review_queue` on the paused state) with roles and groups and the unresolved
   concepts with their evidence; `POST …/checkpoint` takes `{accept, discard, resolutions:
   {concept: answer}, owners: {asset: "Name <email>"}}` and hands them to `_build_decision`
   and `_resume_pipeline` (or `_discard_pending`) — the same code the flags reach.
4. **Events come from the evidence.** `GET …/events?after=N` returns the run's trace lines
   (the JSONL the CLI writes) from line N plus status transitions; an SSE variant streams the
   same. Nothing is recorded twice.
5. **Graphs:** `GET …/model` returns the model as JSON, its Mermaid (`build_model_mermaid`)
   and — new — the **input** model as a Mermaid `erDiagram` of the declared schema with its
   foreign keys (`ui.graphs.build_source_mermaid`), names escaped as the report escapes them.
   `GET …/report` returns `build_report(state)`. `GET …/artefacts` lists the output directory;
   a path under it is served, nothing outside it.
6. Every endpoint has a keyless test through the stub agents the CLI tests use
   (`cli.build_graph` monkeypatched), the pipeline paused at the human checkpoint and resumed.

## 3 Guards before the change

1. Projects: create, list, get; a schema upload that `load_source_schemas` refuses answers 400
   with the loader's message and leaves no file.
2. A run started with `?wait=true` on the stub agents ends `paused`; its `run.json` names the
   thread and the CLI equivalent; `pending.json` exists in the run directory.
3. The checkpoint shows the stub's unassigned contract owner as a decision; a `POST` with an
   owner and `accept` resumes to `finished`; the artefacts list the report and the review
   queue; `pending.json` is gone; `run.json` carries the resume's CLI equivalent.
4. `GET …/model` returns hubs and a Mermaid string containing a hub id, and an `erDiagram`
   for the declared schema naming a table and a foreign key.
5. `GET …/events?after=0` returns trace lines including the route event; a second start while
   one runs answers 409.
6. A path outside the run directory answers 404.

## 4 Pre-registration

A `health_insurance` run driven end-to-end through the API with a real key (one paid run, ≈ 0.5
USD) produces the same artefacts as the CLI (`report.html`, `review-queue.md`, the dbt project)
and the same review queue — the API is a surface, not a second pipeline.

## 5 Not in this WP

The frontend (WP67); the chat console; cancellation of a running task; authentication (local
only); parallel runs.

## 6 Results

*(appended after the change)*

**2026-10-11 — built, keyless and verified with a real key.** Guards `8e2caec` (failing on
import), change `51dbb23`, chapter 14 `38d9f72`, the rest of the docs in the commit carrying this
line. `vault_agent.ui` (`projects`, `runs`, `graphs`, `app`), the `ui` command, extra `ui`. Six
guards pass on the CLI tests' stub agents. **§4 run:** `health_insurance` driven end-to-end
through the API with the real agents (Sonnet 5.5 / Opus 5.5): paused after 39 s at the
checkpoint with 9 decisions and 12 disclosures, accepted through `POST …/checkpoint`, finished;
39 artefacts (the report, the ADR, the dbt models), 4 hubs / 3 links / 7 satellites, 7 calls,
0.13 USD; `run.json` carries `vault-agent run … --out …` and `vault-agent resume --out … --accept`.
The case declares no source schema, so the input `erDiagram` was empty there — the keyless guard
covers it with a two-table schema.
