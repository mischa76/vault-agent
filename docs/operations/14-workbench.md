# 14 The workbench (WP66 backend, WP67 frontend)

The pipeline as a local web application (ADR-0014, WP65): a FastAPI backend over the CLI's
internals (WP66) and a single-page frontend over that API (WP67). The backend never
re-implements the CLI: a run started here is the same run the CLI
starts, pauses at the same checkpoint, and every action the API takes is recorded as the CLI
invocation it is equivalent to (`run.json`, `cli_equivalents`).

## 14.1 Starting it

```bash
uv sync --extra dev --extra demo --extra ui   # fastapi + uvicorn
(cd frontend && npm ci && npm run build)      # the bundle, once (needs Node 22; see 14.4)
uv run vault-agent ui --root workbench --port 8765
```

Binds to `127.0.0.1` only. `--root` is the folder holding the projects; it is created. Open
`http://127.0.0.1:8765/` — without a built bundle the page says so and names the build command;
the API (`/docs`) works either way.

## 14.2 Projects are folders

`<root>/<id>/project.json`, `inputs/` (the requirements document, the declared schema, an
optional profiling file), `runs/<stamp>/` — each run's output directory, exactly what
`vault-agent run --out` writes, plus `run.json`. A schema file is validated on upload with the
house loader; a malformed one is refused with the loader's message before any model is called.

| Endpoint | Does |
|---|---|
| `GET /api/projects` · `POST /api/projects {name}` · `GET /api/projects/{id}` | the store |
| `POST /api/projects/{id}/files {kind, name, content}` | `requirements` (.md/.txt/.pdf), `schema` or `profiling` (.yml/.yaml/.json) |
| `POST /api/projects/{id}/runs {requirements, schema?, existing_run?}` `?wait=true` | start a run (brownfield when `existing_run` names an earlier run of the project); 409 while another run is active |
| `GET /api/runs/{id}` | `run.json`: status `running / paused / finished / failed / crashed / interrupted / discarded`, thread, inputs, `cli_equivalents` |
| `POST /api/runs/{id}/cancel` · `POST /api/runs/{id}/continue` `?wait=true` | WP69: stop the running task (the thread stays, status `interrupted`), and continue an interrupted or crashed run at its latest checkpoint — `vault-agent resume --out <run>`; `discard` through the checkpoint endpoint drops it |
| `GET /api/runs/{id}/events?after=N` | the run's trace lines from line N (the JSONL the CLI writes) and the status |
| `GET /api/runs/{id}/checkpoint` | `phase` — `resolution` (before the modeler: `links` — proposed links, relationship tables and key licenses with key, kind, target, note and evidence; `resolutions` — pending entity resolutions with claim and evidence; `answers`) or `signoff` (the review queue, decisions first, `blocked`, the unresolved mapping concepts) — WP71 |
| `POST /api/runs/{id}/checkpoint {accept, discard, resolutions: {concept: answer}, owners: {asset: "Name <email>"}, links: {"Table.Column": true\|false}}` `?wait=true` | the decision — through `_build_decision` and `_resume_pipeline`, or `_discard_pending`; `links` is `--link` / `--no-link` (WP71); `run.json` records which pause it answered (`checkpoints`) |
| `GET /api/runs/{id}/artefacts` · `GET /api/runs/{id}/artefacts/{path}` | the output directory (never `.vault-agent/`, never outside it) |
| `GET /api/runs/{id}/model` | the model as JSON, its Mermaid flowchart, and the **input** schema as a Mermaid `erDiagram` with foreign keys |
| `GET /api/runs/{id}/report` | the WP11 report |

Run ids are `<project>:<stamp>`. A paused run's state is read from its checkpoint, a finished
run's from `.vault-agent/state.json` (written when it finishes, beside the trace — the same
sensitivity, never published), so a restarted server serves both. One active run per process:
the checkpointer and `pending.json` are single-slot per directory. A second start answers 409.

**Two pauses in a grounded run (WP71).** With a declared schema the pipeline pauses first at
the resolution checkpoint, before the modeler — key licenses from declared foreign keys, link
proposals, entity resolutions — and again at sign-off. The CLI tells them apart with
`_paused_at_resolution` and its interactive loop answers both; the API's `phase` is that
predicate, and a decision at the resolution phase carries `links` and `resolutions`, never
owners (they are applied at sign-off). Everything left as proposed is ratified by `accept`, as
`--accept` does. The frontend opens the next phase when the run pauses again.

**Cancel, interrupt, continue (WP69).** Cancelling a running run stops its task and leaves the
thread's latest checkpoint in place, exactly as a crash does: `pending.json` gets the CLI's
`crashed` phase with the error `cancelled from the workbench`, the status becomes
`interrupted`, and `continue` re-executes the node that was running — the same
`vault-agent resume --out <run>` the terminal would run, recorded as such. When the server
itself dies mid-run, the next start reconciles: a `run.json` left at `running` with a thread and
a checkpoint database becomes `interrupted` (continuable), one without becomes `failed`. Run
one server per root — two on the same root would reconcile each other's runs.

## 14.3 What it does not do

Decide anything the agents or the human decide; call a model from the API process (the run
does); serve beyond localhost; render model text — the JSON is raw, the Mermaid sources and the
report escape as the report always has. Cancellation, parallel runs and the frontend (WP67)
were not in the first phase; WP67 and WP68 brought the first two, WP69 cancellation and
restart robustness. Parallel runs remain out.

## 14.4 The frontend (WP67)

`frontend/` is a Vite + React + TypeScript + Tailwind application; `npm run build` writes it to
`src/vault_agent/ui/static/`, which is gitignored and shipped in the wheel as a build artifact
(the release workflow builds it). For development, `npm run dev` serves it on Vite's port with
`/api` proxied to a running `vault-agent ui`. Its own checks: `npm run check` (TypeScript),
`npm test` (Vitest — the trace derivations, the router, the review grouping); CI runs them in a
separate Node job, the Python suite stays Node-free.

**The build is a snapshot, and nothing tells you it is stale.** `npm ci` and `npm run build`
run once and exit; no Node process stays behind — the only server is `vault-agent ui`
(uvicorn), which serves the API and the built files from `static/`. After a `git pull` that
touches `frontend/`, the server keeps serving the old bundle without a hint: the page simply
looks like before. Rebuild, then reload:

```bash
(cd frontend && npm run build)     # npm ci again only if package-lock.json changed
```

`npm run dev` (Vite on its own port, `/api` proxied to the running server) is for working on
the frontend itself, not for using it.

The layout: a navigation pane (projects → runs), a workspace with **perspectives**, and a right
pane with the syslog-style event stream and, below it, the console (14.6). The footer
is the status line: run state, elapsed, calls, tokens.

| Perspective | Shows | Acts |
|---|---|---|
| Project | name, inputs, run history | create, attach `.md`/`.txt` requirements and `.yml`/`.json` schemas (a PDF goes through the CLI), start a run — greenfield or extending a finished run of the project |
| Run | the graph's nodes as a status strip **derived from the trace** (dashed nodes make no model calls and are inferred), tokens and calls, the run's `cli_equivalents` | open the checkpoint; cancel a running run; continue or discard an interrupted or crashed one (WP69) |
| Review | at the resolution phase: the proposed links, relationship tables and key licenses with build/decline (build is the default, as the CLI's prompt), the entity resolutions with an answer field; at sign-off: decisions first with an owner input per contract (on the item's `asset`), unresolved concepts with their evidence, disclosures folded | ratify and build the model; accept, record without accepting, discard — the same `POST …/checkpoint` the CLI flags reach |
| Model | the output model and the input `erDiagram`, the inventory, a construct's definition | select a construct |
| Artefacts | the output directory as a tree; text files in place, the report in a sandboxed iframe | open raw |
| Log | every trace line, filterable by kind, tool and text | — |

What it does not know: anything the API does not say. Node order and tool names come from
`GET /api/graph`; there is no price table in the bundle (tokens, not money); model text is
rendered as text, Mermaid runs under `securityLevel: 'strict'` as the report does.

## 14.5 Replaying a workbench run from the terminal

Every action is recorded in `run.json` as the CLI invocation it is equivalent to and shown in
the Run perspective — a run driven from the browser reads, for example:

```
vault-agent run <root>/<project>/inputs/requirements.md --out <root>/<project>/runs/<stamp>
vault-agent resume --out <root>/<project>/runs/<stamp> --owner 'customer=Jane Doe <jane@example.com>' --accept
```

## 14.6 The console (WP68)

The right pane's console explains a run from its state — deterministically, with no model
call, and it never runs or decides anything. It answers for a paused run and for a finished
run of this server session (a finished run's state is not reloaded after a restart; the
artefacts are). Commands, also listed by `help`:

| Command | Answers |
|---|---|
| `status` | run status, modeler attempts, validation result, model counts, what the checkpoint holds |
| `items [decisions\|disclosures]` | the review queue, numbered — the numbers are positions in the queue |
| `explain <n>` · `explain <asset>` · `explain <CODE>` · `explain <flag_kind>` | what an item means (kind and role, WP43), how to answer it and the CLI flag that does; a gate's meaning and whether it fired here, with the remedy; a flag kind's meaning and where it was raised |
| `why <construct>` | every issue (code, message, remedy, what it retires), flag (kind, reason), review item and retirement that concerns a hub, link or satellite, with the attempt count |
| `show <construct>` | the construct as the model carries it — key, source entity, feeds, satellites and links of a hub; participations and driving key of a link; parent, type and attributes of a satellite — and its concerns |
| `gates` · `gate <CODE>` | the validator's catalogue (`rules/catalogue.py`, every code the validator emits) and which gates fired in this run |
| `flags` | the typed flags of this run by kind |
| `steering [id]` | the prompt steering the modeler was given — id, backstop, origin (WP16's registry, `active_modeling_rules()`) |
| `cli` | the CLI commands the run is equivalent to so far |
| `what if accept` · `what if discard` · `what if owner <asset>=<Name <email>>` · `what if resolve <concept>=<answer>` | the `vault-agent resume …` command that action would be, with the option's own help text — **nothing runs**; the Review tab performs it |

Free text that names a construct, a gate code, a flag kind or an item's asset is routed to the
matching command; anything else answers with the help. Answers carry jumps to the perspective
where the thing is (open Review, open Model). The catalogue's one-liners are the product's
short answer; chapter 8 remains the manual with the history behind each gate. The transcript
lives in the page for the session; it is not an artefact of the run.
