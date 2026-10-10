---
type: spec
status: proposed
updated: 2026-10-11
---

# WP65 — Workbench UI: kick-off, perspectives, API and phases

Status: **Proposed** (2026-10-11, user: „ich möchte gerne eine GUI-Komponente für vault-agent
bauen die vom design her ein mix von claude desktop und proxmox environment ist …“) · Owner:
Mischa Eismann · Author: Claude. Depends on ADR-0014 (proposed) and on the owner's three
decisions in §6. Nothing here is built.

## 1 What the owner asked for

A GUI with a navigation frame, a visualisation frame and a frame for the conversation with the
agent and the system log; several perspectives; a workflow that carries the user through the
whole procedure: new project → attach requirements and source-system definition → run the
generator with status, information and progress → handle the human-in-the-loop interactions →
inspect input and output objects → see the data-model graphs.

## 2 The perspectives

| Perspective | Shows | Acts | Source today |
|---|---|---|---|
| **Project** | name, folder, requirements document(s), source schema(s), run history | create project, attach/replace files, validate inputs before any LLM call | CLI input checks (`source_schema.load_source_schemas`, malformed-input errors) |
| **Run** | the graph's nodes as a status strip (orchestrator → … → ADR author), attempts, cost and tokens so far, elapsed time | start, cancel, resume | `build_graph`, checkpointer, `TraceEvent`s, usage recorder |
| **Review** | the review queue — decisions first, disclosures after; each item with its evidence | answer an item (resolve concept, set owner), accept, discard | `pending.json`, `_build_decision`, `resume --resolve/--owner/--accept/--discard` |
| **Model** | the output model as a graph (hubs, links, satellites; brownfield: existing vs new); the **input** model as an ER diagram of the declared schema with its foreign keys (new); the extension diff | select a construct → its inventory row, its review items, its generated files | `build_model_mermaid`, `extension_diff`, source schema |
| **Artefacts** | the output directory as a tree: dbt project, contracts, review queue, report, ADR | open, download | files on disk |
| **Log** | the structured log and the trace events as a syslog-style stream, filterable by agent and kind | — | log handler, trace recorder |
| **Chat** | phase 1: a console that explains items, gates and commands from the state; later: an assistant | ask, run a command | state only (phase 1) |

## 3 The API (FastAPI, `127.0.0.1`)

`projects` (CRUD over a folder), `projects/{id}/files` (requirements, schema; validation
result), `runs` (start → background task; `GET` status), `runs/{id}/events` (SSE: trace
events, log lines, node transitions), `runs/{id}/checkpoint` (queue + evidence; `POST`
actions mirroring the CLI flags), `runs/{id}/artefacts`, `runs/{id}/model` (JSON + Mermaid
for both graphs), `runs/{id}/report`. Every mutating endpoint records the equivalent CLI
invocation in the run's `decisions` audit list, so a run driven from the UI is replayable from
the terminal.

## 4 Phases

0. ADR-0014 accepted with the three decisions (§6).
1. Backend API over the CLI internals, keyless tests through the extractor seams; `vault-agent
   ui` starts it. No frontend yet — the API is exercised with the eval harness's stub agents.
2. The shell: three panes, navigation, the Project, Run and Log perspectives; a run of
   `health_insurance` end-to-end from the browser.
3. Review and Model perspectives: the checkpoint handled in the UI; both graphs; the input ER
   diagram is a new renderer beside `build_model_mermaid`.
4. Artefacts and the phase-1 Chat console; the evaluator guide gains a UI path.
5. (Later, own ADR) the LLM assistant; a desktop wrapper.

## 5 What it must not do

Decide anything the agents or the human decide; call a model from the UI process (runs call
models, the UI shows them); expose the server beyond localhost; render model text unescaped.

## 6 The owner's decisions

1. Browser-first local web app (proposed) — or desktop-first?
2. Frontend A (HTMX, no build step) or B (Vite/React/TypeScript/Tailwind)?
3. Chat phase 1 as a state-driven console (proposed) — or an LLM assistant from the start?

## 7 Decisions (2026-10-11)

The owner, asked the three questions: **browser-first, local** (a desktop wrapper later);
**frontend B** — Vite + React + TypeScript + Tailwind; **chat phase 1 as a state-driven console**,
the LLM assistant a later phase with its own ADR. ADR-0014 moves to Accepted. Phase 1 (the
backend API with keyless tests) starts as WP66.
