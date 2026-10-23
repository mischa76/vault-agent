---
type: spec
status: not-measured
updated: 2026-10-11
---

# WP67 — Workbench frontend: the three-pane shell and the perspectives over the WP66 API

Status: **Approved and in progress** (2026-10-11, the owner's go for WP67; ADR-0014 accepted,
frontend B) · Owner: Mischa Eismann · Author: Claude. WP65 phases 2 and 3 plus the Artefacts
perspective of phase 4; the chat console stays WP68. No change to any agent, gate or prompt;
the suite stays keyless; the Python package gains three small API additions, each guarded.

## 1 Scope

A single-page application (`frontend/`, Vite + React + TypeScript + Tailwind, Mermaid as the
report uses it) served by the WP66 app at `/`, with the layout the owner asked for: a
navigation pane (projects → runs), a workspace with perspectives, and a right pane carrying
the syslog-style event stream (the conversation console arrives in WP68 in the same pane).
Perspectives: **Project** (inputs, run history, start a run), **Run** (the graph's nodes as a
status strip derived from the trace, attempts, tokens, elapsed), **Review** (the checkpoint:
decisions first, disclosures after, owners and resolutions entered, accept or discard),
**Model** (the output model's Mermaid and the input `erDiagram`, the inventory), **Artefacts**
(the output directory as a tree, a file opened in place), **Log** (every trace line, filterable
by kind and tool).

## 2 The rules

1. **The frontend knows nothing the API does not say.** Node order comes from `GET /api/graph`
   (the package's `NODES`, each with the tool name its agent emits), never from a list in the
   bundle; counts, statuses and review roles are the API's fields. The strip is *derived from
   the trace*: a node is `done` once a later node's call appears, `active` while its calls are
   the latest, `pending` otherwise; deterministic nodes (orchestrator, checkpoints, code
   generator, validator) are inferred the same way and labelled as inferred.
2. **Every action is an API call the CLI could make**, and the Run perspective shows the
   recorded `cli_equivalents` under the run — the UI never has a path of its own.
3. **Model-derived text is rendered as text** (React's escaping); Mermaid runs with
   `securityLevel: 'strict'` as the report does; nothing is injected as HTML except the
   report, which is shown in a sandboxed iframe from `GET …/report`.
4. **No price in the bundle.** The Run perspective shows tokens and calls from the trace;
   USD belongs to the eval harness, not here (CLAUDE.md: the code owns every number).
5. **The bundle is built, not committed.** `frontend/` builds into
   `src/vault_agent/ui/static/` (gitignored; hatch includes it as an artifact so a wheel
   built after `npm run build` ships it). Without a build, `/` answers a short HTML page
   that names the build command — the API is unaffected.
6. **The suite stays keyless and Node-free:** the Python guards cover the three API additions
   and the static serving; the frontend's own checks (`tsc`, Vitest) run in a separate CI job
   that installs Node. The release workflow builds the bundle before `uv build`.

## 3 Guards before the change

1. `GET /api/graph` returns the nodes in the package's order, and each `tool_name` is the
   `_TOOL_NAME` constant of the agent module that node names (read from the modules, not a
   second list).
2. `GET /api/projects/{id}` carries `runs`: one summary per `runs/<stamp>/run.json`, newest
   first, with `id`, `status`, `started`, `finished`.
3. With a static directory holding `index.html`, `GET /` and `GET /p/anything` (a client
   route) serve it, `GET /assets/x.js` serves the asset, and `/api/…` still answers JSON.
   Without one, `GET /` answers 200 HTML naming `npm run build`.

## 4 Pre-registration

The `health_insurance` example driven through the built frontend in a real browser
(Playwright against the served bundle): create the project, upload the requirements, start,
watch the strip reach the checkpoint, answer the owner decision, accept, see `finished`, the
model graph rendered and the artefacts listed — first keyless on the stub agents (the proof
the shell works), then once with a real key (≈ 0.15 USD, as WP66 §4 cost 0.13). The run's
`cli_equivalents` must read as the two commands WP66 §6 recorded.

## 5 Not in this WP

The chat console (WP68 — the right pane reserves its place); cancellation (needs WP66's task to
be cancellable); a desktop wrapper; authentication; brownfield from the UI beyond choosing an
earlier run as `existing_run` (the API has it; the Project perspective offers it when the
project has a finished run).

## 6 Results

*(appended after the change)*

**2026-10-11 — built, walked keyless and with a real key.** Spec and guards `3c8819b` (red),
the API additions `aa618d6`, the frontend `9225d24`, the docs in the commit carrying this line.
`frontend/` (Vite 8, React 19, TypeScript 5.9, Tailwind 4, Mermaid 11, Vitest 5): the shell,
six perspectives, the trace derivations (`derive.ts`) and the router under Vitest (11 tests),
`tsc` clean, the bundle 3.7 MB with Mermaid's diagrams split into lazy chunks. One finding on
the way: the contract-owner review item carried its contract only in its summary text, so the
Review perspective could not offer an owner input per contract without parsing it — the item
now carries the name as `asset` (orchestrator, guard in `test_wp67_workbench_shell.py`), the
CLI's `review-queue.md` unchanged (the byte fixtures held). **§4, keyless:** the walk
(`frontend/e2e/walk.mjs`, Chromium via Playwright) on the stub agents: project → inputs →
run → paused in 3 s with the strip at `human` → owner entered → accept → finished in 6 s →
model, artefacts (4), log; `run.json` reads `vault-agent run … --out …` and `vault-agent resume
--out … --owner 'customer=Jane Doe <jane@example.com>' --accept`. **§4, real key:** the same walk
on `vault-agent ui` with the real agents (Sonnet 5.5 / Opus 5.5): paused after 45 s with 9
decisions / 11 disclosures, four owners entered in the Review tab, accepted, finished at 48 s;
4 hubs / 3 links / 7 satellites drawn, 40 artefacts, 18 trace lines, 7 calls, 0.14 USD by the
5.5 price table (WP66 §4: 0.13); the two CLI equivalents as pre-registered, with four `--owner`
flags. The input diagram was empty — the example declares no schema (the keyless walk and guard
draw one). **Not measured:** the Review tab's resolution inputs against a brownfield run with
unresolved concepts (no such case in this walk); `npm test` on the `/mnt/c` mount times out
starting its workers and was run from an ext4 copy — CI runs it on its own disk.
