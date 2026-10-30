<div align="center">

# Vault-Agent

**Agentic AI for Data Vault 2.0 — from business requirements to compliant, contract-backed dbt code.**

A multi-agent system that reads requirements documents — optionally grounding against a supplied
source schema — then designs a Data Vault 2.0 model, generates AutomateDV-backed dbt code, and
documents every decision it makes, keeping the rigor of the methodology while removing the
repetitive parts.

[![CI](https://github.com/mischa76/vault-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/mischa76/vault-agent/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB.svg)](https://www.python.org/)
[![Orchestration: LangGraph](https://img.shields.io/badge/orchestration-LangGraph-1C3C3C.svg)](https://langchain-ai.github.io/langgraph/)
[![Codegen: AutomateDV + dbt](https://img.shields.io/badge/codegen-AutomateDV%20%2B%20dbt-FF694B.svg)](https://automate-dv.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Active build](https://img.shields.io/badge/status-active%20build-blue.svg)](#status--roadmap)

</div>

---

## The problem

Data Vault 2.0 is the methodology of choice for enterprise data warehouses that have to stay
auditable, historized, and resilient to change — common in Swiss and DACH banks, insurers, and
pharma. But the *initial* modeling is slow and unforgiving: identifying business keys,
structuring hubs, links, and satellites, and wiring up the loading logic is repetitive,
error-prone work that still consumes senior-architect weeks before a single row is loaded.

The overlap between deep classical Data-Vault practice and modern agentic AI is a genuine
niche — and where this project lives.

## The approach

Vault-Agent treats DV2.0 modeling as a pipeline of specialized agents, each responsible for one
well-defined step, wired together as a LangGraph state machine. A self-correcting validation loop
routes a failing model back to the modeler with the issues as feedback (bounded by a retry cap), and
two human-in-the-loop checkpoints (per
[ADR-0006](docs/architecture/adrs/ADR-0006-human-in-the-loop-review-queue.md)) pause the run: one
*before* modelling, where a human ratifies entity resolutions and links proposed from declared foreign
keys, and one for sign-off — e.g. to assign a data-contract owner — each resuming from a persisted
checkpoint. The methodology rules live in code (not buried in prompts), code
generation goes through the established AutomateDV dbt package rather than hand-written SQL, and
every modeling decision the agents make is captured as an Architecture Decision Record — so the
*reasoning* survives, not just the output.

```
  Requirements (PDF / DOCX / MD)  +  Source schemas (YAML / JSON) [+ profiling]
                          │
                          ▼
        ┌──────────────────────────────────────┐
        │        LangGraph state machine        │
        │   self-correcting loop (built)        │
        │   checkpointing · HITL (built)        │
        └──────────────────────────────────────┘
                          │
   ┌──────────────────────┼───────────────────────┐
   ▼                      ▼                        ▼
 Requirements        Entity Resolver          DV2.0 Modeler
 Parser              Link Proposer            Code Generator
 Business-Key Id.    Resolution Checkpoint    Validator
 Data Contract       Orchestrator             Source Mapper
                                              Human Checkpoint · ADR Author
                          │
                          ▼
   Reviewed dbt project in git  ·  AutomateDV YAML  ·  Data contracts  ·  ADRs
                          │
                          ▼
        Targets:  strategic — Snowflake & MS Fabric · verified by real builds: PostgreSQL,
                  Databricks · builds unchanged on every AutomateDV platform
        Interfaces:  CLI · browser workbench   Observability:  LangSmith traces + evals
```

## The agents

**13 graph nodes**, orchestrated in LangGraph — six model-calling agents (Requirements Parser,
Business-Key Identifier, Data Contract Agent, Entity Resolver, DV2.0 Modeler, Source Mapper's
proposal) and seven deterministic stages (Orchestrator, Link Proposer, Resolution Checkpoint, Code
Generator, Validator, Human Checkpoint, ADR Author; the Source Mapper's re-bind is deterministic
too). All built; the list is `graph.py`'s, which owns it:

| Agent | Responsibility | Status |
|---|---|---|
| **Requirements Parser** | Extracts entities, relationships, and business rules from documents (IREB-aligned output) | ✅ Built |
| **Business-Key Identifier** | Scores key candidates against DV2.0 heuristics; flags ambiguity for review | ✅ Built |
| **DV2.0 Modeler** | Generates Hubs, Links (incl. role-qualified self-referencing links), and Satellites under DV2.0 rules | ✅ Built |
| **Code Generator** | Emits AutomateDV dbt models — hubs, links, standard/multi-active/effectivity satellites, transactional links — plus the staging layer and dbt project scaffolding (a runnable project) | ✅ Built |
| **Validator** | 36 independent `E_` gates (plus advisory `W_` warnings) checking the model and generated artifacts for DV2.0 compliance — the code owns the count: `rg -o '"E_[A-Z_]+"' src/vault_agent/agents/validator.py \| sort -u` | ✅ Built |
| **ADR Author** | Turns the agents' modeling decisions into an explicit, traceable ADR | ✅ Built |
| **Data Contract Agent** | Drafts JSON-Schema source-to-staging contracts + dbt schema tests; flags gaps for human review | ✅ Built |
| **Entity Resolver** | In brownfield runs, proposes whether a new concept is an existing hub (merge / same-as / new), with evidence and a confidence category; nothing merges unratified (WP29) | ✅ Built |
| **Link Proposer** | Deterministic: derives link proposals and key licenses from the source catalogue's declared foreign keys, surrogate→natural-key translations included (WP34–WP42) | ✅ Built |
| **Resolution Checkpoint** | Deterministic: pauses before modelling so a human ratifies the resolver's and proposer's proposals where they can still steer the model (WP29 §2.5) | ✅ Built |
| **Source Mapper** | Proposes which physical source column feeds each business concept (evidence trail, coverage gaps as first-class output); a human ratifies (ADR-0008) | ✅ Built |
| **Orchestrator** | Plans the run (entry node), validates inputs, and assembles the categorized human-review queue | ✅ Built |
| **Human Checkpoint** | Pauses the run at the sign-off gate (LangGraph `interrupt()`) and applies the human's decisions on resume | ✅ Built |

The pipeline self-corrects automatically: a failing validation routes back to the modeler with the
issues as feedback, bounded by a retry cap. On the validated path a human-in-the-loop checkpoint
assembles a categorized review queue and pauses the run (LangGraph `interrupt()`) whenever something
blocks sign-off — a validation error, or a data contract still awaiting an owner. `vault-agent resume`
continues the same run from a persisted SQLite checkpoint once the human decides — including
ratifying proposed source mappings via an editable `mappings.review.yml` (or `--map` for
one-off overrides).

## What you get

- **Speed without sacrificing rigor** — collapse initial DV2.0 modeling from weeks toward hours
- **Reproducible outputs** — reviewed dbt projects in git, never a no-code black box
- **Warehouse-agnostic** — strategic targets Snowflake and MS Fabric (DACH). Today's generator has seed dialects for PostgreSQL (verified, the local demos) and Databricks (`--target-platform databricks`: native seed types, adapter hint — built on a Databricks warehouse since 2026-10-16: the bank demo, the person step and the whole AdventureWorks chain, WP72), and the generated project builds unchanged on every AutomateDV-supported platform (Snowflake, BigQuery, Databricks, MS SQL Server, PostgreSQL). No Fabric-specific dialect exists yet; AutomateDV 0.11.4 ships none
- **Knowledge capture** — every modeling decision documented as an ADR
- **Human-in-the-loop sign-off** — the run pauses for owner assignment and approval, then resumes from a checkpoint
- **A force multiplier, not a replacement** — the architect keeps judgment; the agents do the toil

## Quick start

The pipeline runs end-to-end today: a requirements document in; generated AutomateDV/dbt models,
metadata, data contracts, and an ADR out.

### 1. Install

#### Windows 11 (WSL2)

[`scripts/install/`](scripts/install/README.md) installs the whole stack — WSL2 + Ubuntu, uv,
PostgreSQL, this repo and a keyless smoke test — from one elevated PowerShell script.

#### Linux, macOS, or an existing Ubuntu/Debian

On Ubuntu/Debian, the installer's second stage runs standalone. Otherwise you need git,
[uv](https://docs.astral.sh/uv/) and — for the PostgreSQL demos — a local PostgreSQL:

```bash
git clone https://github.com/mischa76/vault-agent.git
cd vault-agent
uv sync
uv run vault-agent --version                # the released version; see CHANGELOG.md
```

### 2. Your API key

Only a live `run` calls the API. Each developer uses their **own** Anthropic key with active
billing — don't share one across the team (shared keys pool cost on one account, and a single
revocation locks everyone out). Create one at
[console.anthropic.com](https://console.anthropic.com/settings/keys) and put it in your local `.env`
(no quotes, no surrounding whitespace):

```bash
cp .env.example .env
# .env:
ANTHROPIC_API_KEY=sk-ant-api03-…
```

Two failure modes when a `run` can't authenticate: `401 invalid x-api-key` means the key is wrong,
revoked, or (commonly) an older `ANTHROPIC_API_KEY` already exported in your shell is overriding
`.env` — check with `echo "${ANTHROPIC_API_KEY:0:12}… len=${#ANTHROPIC_API_KEY}"` and `unset` it if
it differs; a `400` mentioning *credit balance* means the key is valid but the account has no funds.

### 3. First run (CLI)

```bash
uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

### 4. In the browser: the workbench

The workbench (ADR-0014) is the same pipeline in the browser, every action recorded as its CLI
equivalent (operations manual, chapter 14):

```bash
uv sync --extra ui
(cd frontend && npm ci && npm run build)    # once; Node 22
uv run vault-agent ui --root ~/vault-agent-workbench
```

Keep the root **outside** the repo — runs hold your requirements and contracts. Open
`http://127.0.0.1:8765/`. To look around without a key, start
`uv run vault-agent ui --root demo/workbench-adventureworks` from the repo root: all five
AdventureWorks domains modelled step by step
([`demo/workbench-adventureworks/`](demo/workbench-adventureworks/README.md)).

### Try it without an API key

Most of the project runs keyless — only `vault-agent run` (and the source mapper on grounded runs)
calls the API:

```bash
uv run pytest -q                            # full test suite, green without a key
uv run ruff check . && uv run mypy          # lint + strict type-check
uv run python examples/07_routing.py        # the self-correcting validation loop, deterministic
```

The `examples/` directory also has step-by-step scripts that run each stage in isolation
(`01_simple_requirement.py` … `06_pipeline.py`, these call the API). The two small demo domains
(retail banking and health insurance) are described in [docs/demos/](docs/demos/README.md). To build
a running vault without a key, see [Build the generated vault](#build-the-generated-vault) below.

### Ground the model in a source schema

Supply a **declared source schema** (YAML/JSON listing each source table, its columns and,
optionally, types, foreign keys and primary/unique keys) so proposed business keys and satellite
attributes are cross-checked against columns that actually exist (ADR-0004):

```bash
uv run vault-agent run examples/inputs/bank_account_requirements.md \
  --source-schema examples/inputs/bank_source_schema.yml --out output
```

The file can be read from the source database instead of written — `uv sync --extra catalogue`,
then `vault-agent source-schema --schema Sales --out source_schema.yml` with the SQLAlchemy URL in
`VAULT_AGENT_SOURCE_URL` (metadata only, no row is read; measured on PostgreSQL, WP96).

With a schema the run reports `grounding: on`, emits one data contract per source table, and flags
any key or attribute absent from the schema as a non-blocking `W_*_NOT_IN_SOURCE` warning; without
`--source-schema`, grounding stays inert and the output is unchanged. Declared foreign keys become
link proposals ratified at the first checkpoint (WP34). On a grounded run the **source mapper**
proposes, per business concept, the physical source column that feeds it (ADR-0008 — assist-level,
evidence trail, coverage gaps reported, never guessed); `--profiling <file.yml>` adds column
profiling statistics as evidence. Proposals land in `output/mappings.review.yml` for ratification.
That file too can be read from the source database — `vault-agent profile --schema Sales --out
profiling.yml`: row counts, null and distinct ratios exact over all rows; ranges (numeric and
temporal columns only), lengths and value shapes selectable; example values off by default. It is
a command that reads rows, explicitly invoked and scoped (ADR-0008 #4); the pipeline never
does (measured on PostgreSQL, WP98). For a source without declared keys, `vault-agent infer-keys
--source-schema s.yml --out s.yml` adds what the data says — unique columns and inclusion
dependencies with their evidence — under `inferred_keys`, beside the declarations and never
inside them; the proposer offers them with provenance `inferred`, and `--accept` declines them:
only an explicit `--link` builds one (WP99, ADR-0018; measured against AdventureWorks' own
declarations).

To **extend an existing vault** instead of modelling into an empty one, point the run at an earlier
run's output: `vault-agent run … --existing <earlier output dir>` (brownfield, WP23/WP29).

### Choose the target platform

The vault SQL is the same on every platform — AutomateDV dispatches per adapter. What the generator
knows per platform is the seed column types a contract pins and the adapter hint in the generated
README (operations manual, chapter 9.6).

#### PostgreSQL (default)

Nothing to set: `postgres` is the default and the line verified since 2026-06 — the demos below and
the owner's full AdventureWorks build.

#### Databricks

`--target-platform databricks` writes Databricks' native seed types (`string`, `decimal(38,18)` —
bare `numeric` would be `DECIMAL(10,0)` there and truncate fractions) and names the adapter.
**Verified since 2026-10-16** (WP72): the bank demo, a real run's output, and the whole AdventureWorks
chain built on a Databricks SQL warehouse. The adapter lives in its own extra, `demo-databricks`
(dbt-core 1.11 + dbt-databricks 1.12), which cannot be installed together with the PostgreSQL extra
`demo` — use a second environment ([`demo/bank_databricks/`](demo/bank_databricks/README.md)).

#### Other AutomateDV platforms

Snowflake, BigQuery and MS SQL Server run the generated project unchanged, as far as AutomateDV
does — no build has been recorded on them yet. MS Fabric has no AutomateDV dialect.

### What a run writes

A **runnable dbt project**: raw-vault models (`output/models/raw_vault/`), generated staging models
computing every hash key and hashdiff (`output/models/staging/`), project scaffolding
(`dbt_project.yml`, `packages.yml`, `sources.yml`, a README with run instructions), AutomateDV
metadata (`output/metadata/automatedv.yml`), data contracts and their dbt tests
(`output/contracts/`), an HTML report and a finalized ADR (`output/adrs/`). When the run needs a
human decision it pauses at a checkpoint and writes `output/review-queue.md`; resume it once you've
decided:

```bash
uv run vault-agent resume --out output --owner "customer=Data Team <data@acme.com>" \
  --map "national customer ID=RAW_CUSTOMER.NATIONAL_CUSTOMER_ID" --accept
```

Every run also leaves a **grep-able LLM transcript** at `output/.vault-agent/traces/<thread_id>.jsonl`
— one JSON object per API call with the system prompt (written once per prompt digest), the user
payload, and the tool payload the model returned; a paused run's resume appends to the same file.
Diagnosing a mis-modelled run means reading the trace, not re-running with prints:

```bash
jq -c 'select(.tool_name=="emit_dv_model") | {attempt, payload}' \
  output/.vault-agent/traces/*.jsonl
```

Traces are debug artifacts, **not deliverables**: they contain your raw requirements and
source-schema text, so they stay inside `.vault-agent/` and must not be published with a demo
output. Opt out per run with `vault-agent run … --no-trace`.

### Build the generated vault

The pipeline's output is not just plausible SQL — it is **operable**. The demos take the *real* code
generator's AutomateDV/dbt models, fed a fixed model instead of an LLM, and build a running Data
Vault — no API key, no Docker.

#### On PostgreSQL

[`demo/bank_postgres/`](demo/bank_postgres/README.md) builds two hubs, a standard link, a
self-referencing transactional transfer link (one hub in two roles), two standard satellites and an
effectivity satellite with verified auto end-dating on a local PostgreSQL 16:

```bash
cd demo/bank_postgres
uv sync --extra demo                        # dbt-core + dbt-postgres
uv run python build_vault_models.py         # regenerate raw_vault/*.sql from the generator
DBT_PROFILES_DIR=. uv run dbt deps          # pull AutomateDV
DBT_PROFILES_DIR=. uv run dbt build --full-refresh   # seed + run + test, all green
```

[`demo/mapping_postgres/`](demo/mapping_postgres/README.md) is the **grounded + ratified**
counterpart — the generated staging binds to real, business-named source tables via a ratified
source mapping — and [`demo/fk_links_postgres/`](demo/fk_links_postgres/README.md) builds links
derived from declared foreign keys (translated and relationship-table links).

#### On Databricks

[`demo/bank_databricks/`](demo/bank_databricks/README.md) is the bank demo's twin on a Databricks SQL
warehouse — the same raw-vault SQL, Databricks seed types, host, HTTP path and token from the
environment, built in a second environment with the `demo-databricks` extra.

> The requirements parser, business-key identifier, data-contract agent, entity resolver, modeler
> and source mapper are LLM-driven (Claude, via one shared hardened call path with retry/backoff
> and prompt caching); the link proposer, code/staging generators, validator and ADR author are
> deterministic, so the full test suite (`uv run pytest`) runs without an API key. An eval harness
> (`python -m eval.run`) measures the LLM agents against golden datasets — construct F1,
> driving-key accuracy, mapping accuracy, and gap detection.

## Methodological foundations

This is not vibes-based modeling. The agents are grounded in established practice:

- **Data Vault 2.0** — Dan Linstedt / DataVaultAlliance (methodology and rules)
- **DSAF** — Roelant Vos, Data Solutions Architecture Framework: a pragmatic architecture lens (an influence, not an implemented/selectable mode); adopted ideas and the ADR-gated Vos alternatives are critically mapped in [dsaf-mapping.md](docs/methodology/dsaf-mapping.md)
- **IREB CPRE** — requirements-engineering conventions for the parsing stage
- **Data Contracts** — Chad Sanderson, Mark Freeman & B.E. Schmidt, *Data Contracts: Developing Production-Grade Pipelines at Scale* (O'Reilly, 2025)

## Tech stack

Python 3.12+ · [uv](https://github.com/astral-sh/uv) · [LangGraph](https://langchain-ai.github.io/langgraph/)
· Anthropic Claude API · [AutomateDV](https://automate-dv.com/) · [dbt Core](https://www.getdbt.com/)
· [LangSmith](https://www.langchain.com/langsmith) · pytest · ruff · mypy (strict)

## Status & roadmap

Actively built in the open. The **pipeline runs end-to-end** — CLI and browser workbench — with the
methodology rules in code and a self-correcting validation loop. Its main instrument is AdventureWorks:
a five-step brownfield chain (person → sales, 68 tables) run more than twenty times and built on
PostgreSQL and Databricks; the owner's own step-by-step build of it ships as
[`demo/workbench-adventureworks/`](demo/workbench-adventureworks/README.md). Not yet: a second real
domain, a real customer project. Day-by-day evidence: [`docs/log.md`](docs/log.md).

```
Foundation        repo · architecture · ADRs                                  ✅ done
Core pipeline     requirements parser · business-key id · DV2.0 modeler        ✅ done
Code generation   AutomateDV: hubs · links · sat · ma_sat · eff_sat · t_link   ✅ done
Quality & docs    validator · ADR author · CLI · 2 demo datasets               ✅ done
Routing           self-correcting validation loop (retry on failure)           ✅ done
Grounding         optional source-schema grounding (ADR-0004)                  ✅ done
Contracts         data contract agent + dbt schema tests                       ✅ done
Orchestration     orchestrator entry node · live HITL (interrupt/resume)       ✅ done
Hardening         typed pipeline flags · resilient LLM call path (retry/backoff/caching) ✅ done
Runnable output   staging generator + dbt project scaffolding (verified on Postgres) ✅ done
Validation depth  36 independent validator gates (incl. eff-sat order, HK collisions, composite keys) ✅ done
Evals             eval harness: golden datasets · deterministic scorers · LangSmith layer ✅ done
Multi-role links  role-qualified self-referencing links (ADR-0009, Postgres-verified) ✅ done
Mapping (Phase 2) business↔source mapping — LLM-first, ratified, opacity-probed &
                  Postgres-verified (ADR-0008 Accepted)                        ✅ done
Multi-source hub  business-key harmonisation across sources (WP10, Postgres-verified) ✅ done
Brownfield        extend an existing vault: run --existing, entity resolution,
                  ratified at a checkpoint before modelling (WP23, WP29)       ✅ done
FK-derived links  links and key translations from declared foreign keys (WP34–WP42) ✅ done
Composite keys    composite business and foreign keys end to end (WP45, WP46) ✅ done
Real-data chain   AdventureWorks, five domains, all-green chains; payload, hub-shape
                  and repair-memory gates (WP30, WP49–WP57)                    ✅ done
Model generation  Sonnet 5.5 / Opus 5.5 by default (WP59–WP62)                 ✅ done
Databricks        whole chain built on a Databricks warehouse (WP72)           ✅ done
Self-contained    catalogue and stage bindings travel with the model (WP74–WP77) ✅ done
Workbench         browser UI over the same pipeline, CLI equivalent per action
                  (ADR-0014, WP66–WP71, WP78, WP80)                            ✅ done
Data defects      found in the owner's build and fixed: zero keys for nullable link
                  participants, multi-active on multi-source hubs, satellite-grain
                  gate, hub zero-key rows, homonym keys, evidence-bound link
                  stages (WP83–WP86, WP89, WP90)                               ✅ done
Business Vault    point-in-time tables in our own SQL — AutomateDV deprecates
                  its pit()/bridge() (ADR-0016, WP91); bridges                 ✅ PIT · 🔜 bridge
Second domain     a non-AdventureWorks landscape (bank / insurance)            ⏳ planned
Snowflake         platform profile and a recorded build                       ⏳ planned
```

Every work package has a spec in
[`docs/architecture/backlog-2026-07/`](docs/architecture/backlog-2026-07/README.md); the catalogue
with each one's status is the [work-package table of the documentation index](docs/index.md#work-package-specs).

## Documentation

- [**Documentation index** — the catalogue of everything below](docs/index.md)
- [**Operations manual** (install, run, HITL, gates, warehouse, evals)](docs/operations/README.md)
- [Project log — every closed work package, measurement and correction](docs/log.md)
- [Vision](docs/architecture/0-vision.md)
- [Architecture overview](docs/architecture/1-architecture-overview.md)
- [Multi-agent design](docs/architecture/2-multi-agent-design.md)
- [How requirements become a model (behaviour, assumptions & target)](docs/how-requirements-become-a-model.md)
- [Architecture Decision Records](docs/architecture/adrs/)
- [Automation scope & ambition per layer (ADR-0007)](docs/architecture/adrs/ADR-0007-automation-scope-by-layer.md)
- [Competitive landscape & differentiation](docs/competitive-landscape.md)
- [Source-to-target mapping: scope, premises & the assist boundary (ADR-0008)](docs/architecture/adrs/ADR-0008-source-to-target-mapping.md)
- [Mapping spike: measured evidence & decisions](docs/architecture/backlog-2026-07/spike-mapping-results.md)
- [Eval harness: datasets, scorers, live runner](eval/README.md)
- [Installing on Windows 11 (WSL2)](scripts/install/README.md)
- [DV2.0 rules cheatsheet](docs/methodology/dv2-rules-cheatsheet.md)
- [Demo datasets & walkthroughs](docs/demos/README.md)
- [Contributing — conventions, definition of done, how verification is reported](CONTRIBUTING.md)
## About

Built by **Mischa Eismann** ([eismann.consulting](https://eismann.consulting)) — 20+ years in
ICT, a hybrid technical + business profile, and a CDVP² (Certified Data Vault 2.0 Practitioner).
Vault-Agent is a working exploration of where rigorous data-warehouse practice meets agentic AI.

Questions, ideas, or a DV2.0 modernization to discuss? Open an issue or reach out via
[eismann.consulting](https://eismann.consulting).

## License

MIT — see [LICENSE](LICENSE).
