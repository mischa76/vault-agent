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
| `--existing`, `-e <dir\|file>` | — | **Extend** an existing vault instead of modelling into an empty one (6.7) |
| `--write / --no-write` | write | Write **artifacts** to disk. Run state (checkpoint, `pending.json`, trace) is written regardless — a paused `--no-write` run must stay resumable |
| `--trace / --no-trace` | trace | LLM transcript under `.vault-agent/traces/` (10.2) |
| `--interactive / --no-interactive` | auto | Checkpoint prompt in-terminal; auto = only when run in a TTY |
| `--debug` (global, before the command) | off | DEBUG logging + full tracebacks |

Console output, in order: the execution plan, per-agent progress with construct
counts, a `mode: greenfield` / `extension (N existing construct(s))` line, a
`grounding: on (N source table(s))` / `off` line, the run summary, and — when
the run pauses — the review queue, blocking items first. A malformed
`--source-schema`/`--profiling` fails before any LLM call with an attributable message. An
input document that exists but cannot be read (a Latin-1 `.md`, a corrupt PDF/`.docx`) is
flagged as an error and **skipped**, like an unsupported extension — one bad file in a
multi-document run never takes the run down.

## 6.3 What a run does

Operationally, a run is the topology from 3.2. The stages you see in the console map
to it directly: parse → identify business keys → draft contracts → model → generate →
validate. A line like *validation failed, re-modeling (attempt 2/3)* is the
self-correction loop working — the modeler retries with the validation errors as
feedback, and this is normal, not a fault. Three failed attempts hand the model to the
human-in-the-loop checkpoint (WP25) with everything written for diagnosis (report, review
queue, trace): the run pauses, exits **3**, and you decide — `resume --accept` keeps the
model (the ADR then says it was accepted over its errors) or `resume --discard` drops it.

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
│   ├── automatedv.yml         # construct metadata (machine-readable)
│   └── dv_model.yml           # the LOGICAL model — point a later --existing here (6.7)
├── contracts/
│   ├── <asset>.contract.yml   # one data contract per source asset
│   └── <asset>.tests.yml      # dbt schema tests derived from the contract
├── adrs/
│   └── ADR-0001-<slug>.md     # the model ADR (per-output numbering, WP2)
├── mappings.review.yml        # business↔source mapping — review & ratify (WP9)
├── review-queue.md            # the HITL review queue (chapter 7)
├── extension-diff.md          # extension runs only: unchanged / extended / new (6.7)
├── report.html                # self-contained run report incl. model graph (WP11)
└── .vault-agent/              # run infrastructure, NOT a deliverable
    ├── checkpoints.sqlite     # LangGraph checkpointer (pause/resume)
    ├── pending.json           # while a run is unfinished (paused or crashed)
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
vault-agent [--debug] resume [--out <dir>] [DECISION FLAGS] [--discard]
```

Resume reattaches to the unfinished thread recorded in `pending.json` under `--out`
(default `output`) — same shell or days later, the checkpoint is on disk. `pending.json`
is **single-slot**: one unfinished run per output directory (concurrent runs into one
`--out` are unsupported).

**A paused run** (`phase: paused` — the HITL checkpoint). With **decision flags**
(`--owner`, `--accept`, `--map`, `--mappings` — semantics in chapter 7) it applies the
decision and continues. With **no flags in a TTY** it loads the paused state, re-prints
the review queue, and drives the checkpoint interactively; on a non-TTY it prints the
flag instructions instead.

**A crashed run** (`phase: crashed` — a node raised, WP17). Resume continues the thread
where it stopped: LangGraph re-executes only the failed node, so the completed agents are
not paid for twice. If the continued run reaches the HITL checkpoint it is handled exactly
as above (flags apply immediately, a TTY prompts, a pipe prints the instructions). A run
not worth continuing is thrown away with `--discard`, which deletes the checkpoint thread
and `pending.json` (artifacts already written are untouched).

`resume` takes `--write/--no-write` with the same artifacts-only meaning: a run paused
under `--no-write` says so in its pause message, because resuming **does** write unless you
pass `--no-write` again. `--trace` (default on) appends the resume's LLM calls to the same
transcript.

## 6.6 Exit codes & failure surface

| Code | Meaning | On disk |
|------|---------|---------|
| 0 | Finalized — or paused, which is a normal outcome, not an error | Full artifacts; paused: + `pending.json`, kept checkpoint |
| 1 | Input-file error (before any LLM call), pipeline failure, or `resume` with no unfinished run | Failure after start: artifacts-so-far + report + trace + a `crashed` `pending.json`, so `resume` continues it |
| 2 | CLI usage error (unknown flag, missing argument — Click convention) | untouched |
| 3 | The run completed, but **the model does not validate** — the re-model budget was exhausted and validation errors remain | Full artifacts + `report.html`; paused at the checkpoint, or finalized (with the ADR carrying the error caveat) if a human accepted |

Exit **3** is the one to script against: it means the pipeline itself worked and the
*model* did not. It is returned whether the run is still paused at the checkpoint or a
human accepted it there — accepting does not make an invalid model valid, and the
artifacts on disk still carry the known errors. Three attempts (`MAX_MODELING_ATTEMPTS`)
that all fail validation end at the human-in-the-loop checkpoint, not silently: you can
`resume --accept` to keep the model for diagnosis, or `resume --discard` to throw it away.

Failures print a one-line summary by default; global `--debug` re-raises with the full
traceback. Nothing is ever deleted on failure — a paused or crashed run keeps its
checkpoint and trace for diagnosis (chapter 10) or a later resume.

## 6.7 Extending an existing vault (brownfield mode)

Non-destructive extensibility is the point of Data Vault 2.0, and the everyday enterprise
scenario is not a greenfield build: a new source system starts feeding entities you already
model, or new entities attach to hubs that already exist. `--existing` runs the pipeline in
**extension mode**.

```
vault-agent run crm_requirements.md --out output/v2 \
    --existing output/v1 --source-schema crm_schema.yml
```

`--existing` takes a previous run's **output directory** (its `metadata/dv_model.yml` is
read) or that file directly. An output generated before this file existed cannot be
extended — regenerate that vault once with the current version first; the generator is
deterministic, so the regenerated project is identical. The error message says so.

**What the agent may and may not do.** An extension is additive, and that is enforced, not
merely encouraged:

| The run may | The run may not |
|---|---|
| Add hubs, links, satellites | Remove an existing construct (`E_EXISTING_REMOVED`) |
| Add a source feed to an existing hub | Change an existing hub's business key (`E_EXISTING_BK_CHANGED`) |
| Add a satellite to an existing parent | Change an existing link's grain (`E_EXISTING_GRAIN_CHANGED`) |
| | Reshape an existing satellite — **including adding an attribute** (`E_EXISTING_SAT_RESHAPED`) |

Attribute *growth* counts as a reshape because a satellite that already holds history would
need every past row backfilled. New attributes for an existing parent belong in a **new
satellite** on it — which is what the modeler is steered to produce.

Every legitimate addition also raises an advisory `W_EXISTING_EXTENDED`, so the review queue
(chapter 7) inventories the increment rather than staying silent about it.

**Why regenerating everything is safe.** The generator is deterministic: an untouched
construct renders byte-identically, so rebuilding it changes no table. That promise is made
checkable by `extension-diff.md` (and the report's *Extension* section), which lists
unchanged / extended / new constructs and — the part that matters — **which generated files
actually changed content**, computed by regenerating the existing model alone and comparing.
A hub that starts unioning a second staging model legitimately changes; the diff names that
file.

**Grandfathering.** When a single-source hub gains a feed, its original staging model keeps
its name (`stg_<entity>`) and only the new feed gets the suffixed `stg_<entity>_<source>`;
existing satellites keep their names and their binding. Renaming them would drop and rebuild
tables that hold history.

**The ADR** documents only the delta, plus an *Extends* section naming the vault it extends
and pointing at the diff.

**Known limitation (2026-07-29).** A satellite fed by ONE source of a now-multi-source hub —
the natural shape when a new system brings its own attributes — currently trips
`E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` and is flagged rather than generated. Leave the
satellite's `source_table` unset and it splits per feed instead. Giving the declared-source
form real semantics needs a modelling decision that has not been taken.
