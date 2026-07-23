# 6. Running the pipeline

## 6.1 Inputs

**Requirements document (required).** Markdown, plain text, PDF, or Word
(`.md`/`.txt`/`.pdf`/`.docx`). This is the primary steering input: the parser extracts
business objects and relationships from it, so a document that names its entities,
keys, and relationships cleanly models better than an inventory dump. Documents longer
than `MAX_DOCUMENT_CHARS` (400k chars, ~100k tokens) are cut to the head and flagged
`INPUT_TRUNCATED` — the pipeline continues on the head and you decide at the
checkpoint.

**Declared source schema (optional, recommended).** `--source-schema <file.yml|json>`
activates grounding (2.3): a top-level `source_schemas:` key or a bare list of tables,
each with `table`, `columns` (plain names or objects with `name`/`type`/`comment`),
and optionally `schema`/`database` for physical `source()` binding (9.3). Columns with
types and comments are what the source mapper feeds on — the richer the declaration,
the better the mapping. Malformed entries fail fast with an error naming file and
problem.

**Profiling evidence (optional).** `--profiling <file.yml|json>` adds per-column
statistics (uniqueness, null rate, example values) as mapper evidence. Example values
are the pipeline's one deliberate touchpoint with data *values* — see 10.7 for the
data boundary and when to mask them.

Worked examples for all three live under `examples/inputs/` (bank and messy-insurance
sets, including an enriched schema and profiling file).

## 6.2 `vault-agent run`

```
vault-agent [--debug] run <input_doc> [OPTIONS]
```

| Option | Default | Effect |
|--------|---------|--------|
| `--out`, `-o <dir>` | `output` | Output directory (also holds the run's checkpoint) |
| `--source-schema`, `-s <file>` | — | Ground against a declared schema (6.1) |
| `--profiling <file>` | — | Mapper evidence (6.1) |
| `--write / --no-write` | write | Write artifacts to disk |
| `--trace / --no-trace` | trace | LLM transcript under `.vault-agent/traces/` (10.2) |
| `--interactive / --no-interactive` | auto | Checkpoint prompt in-terminal; auto = only when run in a TTY |
| `--debug` (global, before the command) | off | DEBUG logging + full tracebacks |

Console output, in order: the execution plan, per-agent progress with construct
counts, a `grounding: on (N source table(s))` / `off` line, the run summary, and — when
the run pauses — the review queue, blocking items first. Input-file problems
(unreadable document, malformed schema/profiling) fail before any LLM call with an
attributable message.

## 6.3 What a run does

Operationally, a run is the topology from 3.2. The stages you see in the console map
to it directly: parse → identify business keys → draft contracts → model → generate →
validate. A line like *validation failed, re-modeling (attempt 2/3)* is the
self-correction loop working — the modeler retries with the validation errors as
feedback, and this is normal, not a fault. Three failed attempts end the run as failed
with everything written for diagnosis (report, review queue, trace).

On the validated path the source mapper proposes business↔source bindings (grounded
runs only — ungrounded it is inert), then the checkpoint decides: clean runs finalize
straight through (ADR written, checkpoint thread pruned); runs with blocking items
pause (chapter 7). Where LLM calls happen and what they cost: 5.2; per-call visibility:
chapter 10.

## 6.4 Output anatomy

Everything a finalized run writes below `--out`:

```text
<out>/
├── dbt_project.yml            # runnable project scaffolding (staging views,
├── packages.yml               #   raw-vault incremental, AutomateDV pin)
├── README.md                  # generated run instructions for THIS output
├── models/
│   ├── raw_vault/             # hubs, links, satellites (one .sql each)
│   └── staging/               # stg_* hash/hashdiff models + sources.yml
├── metadata/
│   └── automatedv.yml         # construct metadata (machine-readable)
├── contracts/
│   ├── <asset>.contract.yml   # one data contract per source asset
│   └── <asset>.tests.yml      # dbt schema tests derived from the contract
├── adrs/
│   └── ADR-0001-<slug>.md     # the model ADR (per-output numbering, WP2)
├── mappings.review.yml        # business↔source mapping — review & ratify (WP9)
├── review-queue.md            # the HITL review queue (chapter 7)
├── report.html                # self-contained run report incl. model graph (WP11)
└── .vault-agent/              # run infrastructure, NOT a deliverable
    ├── checkpoints.sqlite     # LangGraph checkpointer (pause/resume)
    ├── pending.json           # only while a run is paused
    └── traces/<thread>.jsonl  # LLM transcript (chapter 10)
```

Conditional artifacts: `mappings.review.yml` only when the mapper produced
proposals/gaps (grounded runs); `review-queue.md` only when there are review items;
`contracts/` only when contracts were drafted. `report.html` is always written — on a
*paused* run it shows the pending state and is overwritten on finalize. The output is
a complete dbt project; what you add to build it (raw data, `profiles.yml`) is
chapter 9.

## 6.5 `vault-agent resume`

```
vault-agent [--debug] resume [--out <dir>] [DECISION FLAGS]
```

Resume reattaches to the paused thread recorded in `pending.json` under `--out`
(default `output`) — same shell or days later, the checkpoint is on disk. With
**decision flags** (`--owner`, `--accept`, `--map`, `--mappings` — semantics in
chapter 7) it applies the decision and continues. With **no flags in a TTY** it loads
the paused state, re-prints the review queue, and drives the checkpoint interactively;
on a non-TTY it prints the flag instructions instead. `--trace` (default on) appends
the resume's LLM calls to the same transcript.

## 6.6 Exit codes & failure surface

| Code | Meaning | On disk |
|------|---------|---------|
| 0 | Finalized — or paused, which is a normal outcome, not an error | Full artifacts; paused: + `pending.json`, kept checkpoint |
| 1 | Input-file error (before any LLM call), pipeline failure, or `resume` with no paused run | Failure after start: artifacts-so-far + report + trace |
| 2 | CLI usage error (unknown flag, missing argument — Click convention) | untouched |

Failures print a one-line summary by default; global `--debug` re-raises with the full
traceback. Nothing is ever deleted on failure — a paused or crashed run keeps its
checkpoint and trace for diagnosis (chapter 10) or a later resume.
