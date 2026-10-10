# 14 The workbench backend (WP66)

The pipeline as a local API, the first phase of the workbench UI (ADR-0014, WP65). It wraps
the CLI's internals and never re-implements them: a run started here is the same run the CLI
starts, pauses at the same checkpoint, and every action the API takes is recorded as the CLI
invocation it is equivalent to (`run.json`, `cli_equivalents`).

## 14.1 Starting it

```bash
uv sync --extra dev --extra demo --extra ui   # fastapi + uvicorn
uv run vault-agent ui --root workbench --port 8765
```

Binds to `127.0.0.1` only. `--root` is the folder holding the projects; it is created.

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
| `GET /api/runs/{id}` | `run.json`: status `running / paused / finished / failed / crashed / discarded`, thread, inputs, `cli_equivalents` |
| `GET /api/runs/{id}/events?after=N` | the run's trace lines from line N (the JSONL the CLI writes) and the status |
| `GET /api/runs/{id}/checkpoint` | the review queue (decisions first), `blocked`, the unresolved concepts with evidence |
| `POST /api/runs/{id}/checkpoint {accept, discard, resolutions: {concept: answer}, owners: {asset: "Name <email>"}}` `?wait=true` | the decision — through `_build_decision` and `_resume_pipeline`, or `_discard_pending` |
| `GET /api/runs/{id}/artefacts` · `GET /api/runs/{id}/artefacts/{path}` | the output directory (never `.vault-agent/`, never outside it) |
| `GET /api/runs/{id}/model` | the model as JSON, its Mermaid flowchart, and the **input** schema as a Mermaid `erDiagram` with foreign keys |
| `GET /api/runs/{id}/report` | the WP11 report |

Run ids are `<project>:<stamp>`. The state of a finished run lives in the process for the
session; a paused run's state is read from its checkpoint, so a restarted server can still
decide it. One active run per process: the checkpointer and `pending.json` are single-slot per
directory. A second start answers 409.

## 14.3 What it does not do

Decide anything the agents or the human decide; call a model from the API process (the run
does); serve beyond localhost; render model text — the JSON is raw, the Mermaid sources and the
report escape as the report always has. Cancellation, parallel runs and the frontend (WP67)
are not in this phase.
