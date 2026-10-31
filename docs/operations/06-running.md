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
optionally `schema`/`database` for physical `source()` binding (9.3), and optionally the
table's own `comment` (WP97). Columns with types and comments, and the table's comment, are
what the source mapper and the entity resolver feed on — the richer the declaration, the
better the mapping; the modeler's prompt shows table and column names only. Malformed entries fail fast with an error naming file and
problem.

**Reading the declared schema from the source database (WP96, C27 stage 1).** Instead
of writing the file, read it from the catalogue:

```bash
export VAULT_AGENT_SOURCE_URL='postgresql+psycopg2://user:pass@host:5432/db'
uv run vault-agent source-schema --schema Sales --schema Person --out inputs/source_schema.yml
```

needs `--extra catalogue` and the dialect's driver (4.2). It transcribes what the
catalogue says about the named schemas — every table (views with `--views`), every
column in order with the vendor's type spelling and `nullable`, table and column comments verbatim,
the primary key, unique constraints and unique indexes, foreign keys with their schema —
into exactly the file `--source-schema` reads, with a header naming the connection
(password hidden). Nothing is inferred and no row is read (10.7); the file is yours to
edit afterwards. Two reads of one catalogue give one byte-identical file. Without
`--schema` the command lists the schemas the connection sees and exits 2; a missing driver
or a refused connection exits 1. A type the dialect has no class for is declared empty
and named on stderr, never guessed — except the ones the reader registers per vendor
(PostgreSQL `xml`), spelled as the catalogue spells them. The source types of a
customer's catalogue are the warehouse's problem only where a stage casts (9.3); the gates
read type families, which the vendor spelling keeps.

**Profiling evidence (optional).** `--profiling <file.yml|json>` adds per-column
statistics (uniqueness, null rate, example values) as mapper evidence. Example values
are the pipeline's one deliberate touchpoint with data *values* — see 10.7 for the
data boundary and when to mask them.

**Reading the profiling evidence from the source database (WP98, C27 stage 2).** The
one command that reads rows — the explicitly invoked, read-only, scoped step ADR-0008 #4
permits; the pipeline itself still reads none:

```bash
uv run vault-agent profile --schema Sales --table Sales.SalesOrderHeader --out inputs/profiling.yml
```

same URL and extras as `source-schema`. Per table the row count, per column the null
ratio, the distinct count and the uniqueness ratio (distinct ÷ non-null) — exact over
all rows, by SQL aggregates — into exactly the file `--profiling` reads. Beyond the
counts, `--check` selects (repeat; default `range`, `lengths`, `patterns`; `none` for
counts only): `range` writes `min`/`max` on numeric and temporal columns only — never on
a character column, whose minimum is a row value; `lengths` the shortest and longest
value of a character column; `patterns` its five most frequent value shapes (digits `9`,
letters `A`, the rest kept) with their share, from a sample of the first `--sample` rows
the database returns (10 000; the counts are never sampled); `--examples K` writes K
example values per column and is off by default, because it is the one check that
writes a character column's values. A column the database refuses — PostgreSQL has no
equality operator for `xml` or `json`, so `count(distinct)` fails — is omitted and
named on stderr, never written as zero; a statistic that could not be measured (the
minimum of an empty table) is absent. `--table` narrows to a candidate set (ADR-0008 #2),
`Schema.Table` or a bare name. Exit codes as `source-schema`: no `--schema` lists the
schemas and exits 2, a schema or table the catalogue lacks and an unknown check exit 2,
a missing driver or a refused connection exits 1. Two runs on one database give one
byte-identical file (measured on the AdventureWorks data copy, 68 tables, 2026-10-30).
What the file carries and when to drop `range`: 10.7. The new fields reach no model
input; the mapper and the validator read what they read before.

**Inferring keys from the data (WP99, C27 stage 3, ADR-0018).** A source without declared
keys — a dump of data without its DDL, a lake — leaves the link proposer blind. The second
command that reads rows writes what the data says beside the declarations, never inside them:

```bash
uv run vault-agent infer-keys --source-schema inputs/source_schema.yml --out inputs/source_schema.yml
```

reflects every table the file names and adds an `inferred_keys:` block per table: `unique` —
the columns unique and non-null over every row (more than one row; never a declared key) —
and `foreign` — inclusion dependencies, a column every non-null value of which occurs in a
key column (declared or inferred unique) of the same type family, each with its evidence:
the rows checked, the distinct values on both sides, the candidate tier, the `tied` key
columns with exactly the same number of distinct values (equal domains — tables keyed 1:1 on
one id — which data alone cannot tell apart; the tie is broken by a stated preference, a key
named after its own table first, and the proposer tries the tied and the wider ones for an
existing hub), and the `wider` key columns that contain every value with more (the inference
is the tightest; an employee is a person before it is a business entity). One inference per
column. Which pairs are checked, `--candidates`: `name`
(default) — the same compact name, a name ending in the key's (`ShipToAddressID` →
`AddressID`), or the key table's name plus `ID` (`SalesPersonID` → `SalesPerson`'s key);
`type` — every pair of the same type family, complete and noisy (a two-valued status column is
contained in every integer key) and expensive (one anti-join per pair). A pair the catalogue
declares is never inferred. The proposer reads the block as proposals with provenance
`inferred`, and **`--accept` declines them**: only `resume --link Table.Column` or a *yes* at
the prompt (whose default for an inferred proposal is *no*) builds one (7). Two reads of one
database give one byte-identical file; measured against AdventureWorks' own declarations on
the key-less data copy (`docs/log.md`, 2026-10-30).

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
| `--target-platform <name>` | `postgres` | Warehouse the generated project is aimed at (9.6): seed column types and the README's profile hint. The vault SQL is platform-neutral. Values: the `TargetPlatform` members in `rules/platforms.py` |
| `--primary-model <id>` · `--heavy-model <id>` · `--anthropic-base-url <url>` | from `.env` | WP113 (C3): pin this run's models (the heavy one is the modeler's) and an Anthropic-compatible endpoint over `PRIMARY_MODEL`, `HEAVY_MODEL`, `ANTHROPIC_BASE_URL`; recorded in the run's `pending.json`, so `resume` and `continue` build the same agents — they take no such flags |
| `--naming-profile <file.yml>` | house style | WP114 (C3): the physical names the generator writes — `staging_prefix`, `hashkey_suffix`, `hashdiff_suffix`, `load_datetime`, `record_source`, `applied_dts`, `technical_case` (`upper`/`lower`); the default is what every fixture and chain was generated under. A non-default profile is written to `metadata/naming.yml` beside the model; an extension (`--existing`) adopts its vault's profile and refuses a different one |
| `--pit / --no-pit` | off | WP91 (ADR-0016): generate a point-in-time table per hub with two or more descriptive satellites under `models/business_vault/` (9.7); needs both bounds below. Off, every artifact is what it was |
| `--as-of-start <YYYY-MM-DD>` · `--as-of-end <YYYY-MM-DD>` · `--as-of-grain day\|month` | — · — · `day` | The as-of spine every PIT reads: start inclusive, end exclusive (`dbt_utils.date_spine`); `--pit` without both is a usage error, no LLM token spent |
| `--write / --no-write` | write | Write **artifacts** to disk. Run state (checkpoint, `pending.json`, trace) is written regardless — a paused `--no-write` run must stay resumable |
| `--trace / --no-trace` | trace | LLM transcript under `.vault-agent/traces/` (10.2) |
| `--interactive / --no-interactive` | auto | Checkpoint prompt in-terminal; auto = only when run in a TTY |
| `--debug` (global, before the command) | off | DEBUG logging + full tracebacks |

Console output, in order: the execution plan, per-agent progress with construct
counts, a `mode: greenfield` / `extension (N existing construct(s))` line, a
`platform: <name>` line, an `llm route: <provider …>` line (5.5), a
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
Across the attempts the loop keeps what a deterministic remedy decided (WP44): a hub the
`E_HUB_HK_COLLISION` remedy retired is refused if a later attempt re-emits it — under its name or
under another one on the same source entity with the same key (WP49) — together with
the links and satellites that named it; the refusal shows up as a `retired_reemitted`
disclosure, an orphaned dependent as a `retired_orphan` decision in the review queue. Likewise
(WP46) a satellite the key gate refused is retired by its shape — re-emitted unchanged, it is
dropped into a `retired_orphan` decision; re-parented, it is judged afresh. And (WP48) an attribute
two satellites of one relation both carry is kept on one of them by the overlap remedy and retired
on the others — re-emitted there, it is dropped again, a disclosure. And (WP50) a hub the
wrong-column gate recognises as the second hub of an entity the checkpoint already resolved a key
to is retired by shape; re-emitted, it goes with its links and satellites, the payload a decision.
When the remedy kept a twin of the dropped hub (WP51), its satellites and link participations move
to the twin instead — a `retired_reparented` disclosure; only a link the twin already takes part in
is dropped. And (WP52) a satellite the key gate refused whose remedy named **exactly one** parent
carrying the relation's key moves to that parent when re-emitted unchanged — the same disclosure;
with no or several candidates the `retired_orphan` decision stands.

Since WP57 (2026-10-09) a retry is a **repair, not a new draft**: the payload carries the modeler's
own previous model (`previous_model` — the delta, never the vault) beside the issues, and a
steering line asks for exactly the changes the issues name, keeping every construct no issue
names. Until then every attempt was drawn afresh from the same inputs, and what one attempt got
right survived into the next only by chance (the tenth chain's step 3). The system prompt is
unchanged across retries, so the prompt cache still hits; the payload grows by the model.

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
read, and since WP74 its `metadata/source_catalogue.yml` beside it — the declared tables every
earlier increment bound to, so the existing constructs' staging keeps its relations and source
blocks and the extended project parses whole) or that file directly. An output generated before this file existed cannot be
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

When the modeler's delta *re-states* an existing hub with a different key, or an existing link or
satellite under its own name, the merger keeps the vault unchanged and raises an
`extension_conflict` flag — a review **decision** (chapter 7): did you mean a new satellite, and
what of the re-stated payload is lost? Since WP52 that flag is `advisory`, not `error`: nothing
is wrong with the generated vault, and `pipeline_health` no longer scores the run 0.0 on it.

Every legitimate addition also raises an `I_EXISTING_EXTENDED` record (severity `info`), so
the validation report inventories the increment rather than staying silent about it. Since WP43
that inventory is *not* a review item — the review queue (chapter 7) lists decisions and
disclosures only; read the increment in `extension-diff.md` or the report's Extension section.

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
tables that hold history. On every later step the carried catalogue's `stage_bindings` says which
feed is the grandfathered one, so the name holds beyond the step that added the feed; an existing
satellite's payload is staged from that feed alone, and when no such binding is carried the
satellite is flagged for review rather than bound to a guessed feed (WP101, 2026-10-30).

**The ADR** documents only the delta, plus an *Extends* section naming the vault it extends
and pointing at the diff.

**Attributes that come from only one source.** When a new system brings its own attributes
to an entity the vault already models, give that satellite a `source_table` naming the new
feed: it is then generated once and reads that feed's staging (ADR-0011) — the canonical
DV2.0 one-satellite-per-source shape. Leave `source_table` unset only when the attributes
really do arrive from *every* feed; the satellite then splits across them. A `source_table`
naming a table that is not one of the hub's feeds is an error, and the message lists the
feeds you can name.
