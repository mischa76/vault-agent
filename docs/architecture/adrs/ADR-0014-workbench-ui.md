# ADR-0014: A workbench UI for vault-agent — a local web application over the pipeline

**Status:** Proposed
**Date:** 2026-10-11
**Decision makers:** Mischa Eismann

## Context

The pipeline runs end-to-end (seven green 4.x chains, five green 5.5 chains; two demos built on
PostgreSQL), which is the condition CLAUDE.md sets before any UI work. Today the user drives it
through the CLI: `run`, a pause at the human-in-the-loop checkpoint, `resume` with flags
(`--accept`, `--discard`, `--resolve concept=hub`, `--owner`), and reads the results as files —
`review-queue.md`, `report.html` (WP11, a Mermaid graph of the output model), `dv_model.yml`,
contracts, the dbt project, `.vault-agent/traces/*.jsonl`. An external evaluator (the evaluator
guide, 2026-10-09) meets the same surface. The owner wants a workbench that supports the whole
procedure: create a project, attach the requirements document and the source-system definition,
run the generator with status and progress, handle the checkpoint, inspect inputs and outputs,
and see the data-model graphs — in a layout mixing Claude Desktop (navigation, workspace, chat)
and the Proxmox console (perspectives, status, a log pane).

Constraints: Python 3.12 and `uv` are the project's toolchain; the suite must stay keyless; the
LangGraph checkpointer and `pending.json` define run state per output directory (single slot);
every model-derived string is hostile and is escaped (the report's rule); nothing in the UI may
decide what the agents decide — it presents, asks and records.

## Decision (proposed)

1. **A local web application, one process.** A FastAPI backend inside the package
   (`vault_agent.ui`) exposes the pipeline as an API — projects, runs, events, checkpoint,
   artefacts, graphs — and serves a single-page frontend. It binds to `127.0.0.1` only. A desktop
   wrapper (Tauri or pywebview) can come later without changing the API; the browser is the
   first target because it needs no second runtime.
2. **The backend reuses the CLI's internals, never re-implements them:** `build_graph` with the
   per-directory checkpointer, `pending.json`, `_build_decision`/`resume` paths, `build_report`
   and `build_model_mermaid`, the trace recorder as the event source. Progress and the log pane
   stream `TraceEvent`s and the structured log over server-sent events. Every endpoint has a
   keyless test through the injectable extractor seams the eval harness already uses.
3. **The frontend is a three-pane workbench:** navigation (projects → runs → artefacts), a
   workspace with **perspectives** — Project, Run, Review, Model, Artefacts, Log — and a right
   pane for the conversation with the agent and the syslog-style event stream. Frontend stack:
   *to be decided* (see alternatives); the API contract is the same either way.
4. **Chat is phased.** Phase 1 is a command and explanation console (what each review item
   means, what a gate refused, what a command would do — all from the state, no model call).
   An LLM-backed assistant over the project state is a later phase with its own cost line.

## Alternatives considered

- **Frontend A — server-rendered HTMX + Alpine + Mermaid, no build step.** Pros: one toolchain,
  fits `report.py`, trivial to test in Python. Cons: resizable multi-pane perspectives, live
  graph interaction and a chat pane are awkward; the Claude-Desktop feel is hard to reach.
- **Frontend B — Vite + React + TypeScript + Tailwind, Mermaid (parity with the report) or an
  interactive graph library.** Pros: the layout and interactions the owner describes are
  natural; perspectives are routes. Cons: a Node toolchain and a second test stack (Vitest,
  Playwright) in a Python repo; more code to keep honest.
- **Python-native GUI (NiceGUI, Reflex, Textual).** Pros: no JavaScript. Cons: frameworks with
  their own opinions and lifecycles; graph rendering and the three-pane shell fight them.
- **Desktop-first (Tauri/Electron).** Deferred: it wraps the same API; nothing is lost by
  starting in the browser.

## Consequences

- A new top-level surface with its own spec series (WP65+), its own tests and its own entry in
  the operations manual; the CLI stays the reference behaviour and the UI is measured against
  it (every action the UI takes must be expressible as a CLI invocation it records).
- The single-slot `pending.json` per output directory becomes „one run at a time per project“
  in the UI; parallel runs need separate projects.
- Model-derived text reaches a browser: the report's escaping rules become API rules.
- The frontend choice (A or B) is the one decision this ADR leaves open; it is the owner's.
