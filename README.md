<div align="center">

# Vault-Agent

**Agentic AI for Data Vault 2.0 — from business requirements to compliant, contract-backed dbt code.**

A multi-agent system that reads requirements documents — optionally grounding against a supplied
source schema — then designs a Data Vault 2.1 model, generates AutomateDV-backed dbt code, and
documents every decision it makes, keeping the rigor of the methodology while removing the
repetitive parts.

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
a live human-in-the-loop checkpoint (per
[ADR-0006](docs/architecture/adrs/ADR-0006-human-in-the-loop-review-queue.md)) pauses the run for
sign-off — e.g. to assign a data-contract owner — then resumes from a persisted checkpoint. The methodology rules live in code (not buried in prompts), code
generation goes through the established AutomateDV dbt package rather than hand-written SQL, and
every modeling decision the agents make is captured as an Architecture Decision Record — so the
*reasoning* survives, not just the output.

```
  Requirements (PDF / DOCX / MD)  +  Source schemas (SQL / DDL)
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
 Requirements        DV2.0 Modeler            Data Contract
 Parser              Business-Key Id.         Validator
 Code Generator      ADR Author               Orchestrator
                          │
                          ▼
   Reviewed dbt project in git  ·  AutomateDV YAML  ·  Data contracts  ·  ADRs
                          │
                          ▼
        Targets:  Snowflake & MS Fabric (focus) · runs on any AutomateDV platform
                  (Snowflake · BigQuery · Databricks · SQL Server · Postgres demo)
                 Observability:  LangSmith traces + evals
```

## The agents

Eight specialized agents, orchestrated in LangGraph — **all eight built**:

| Agent | Responsibility | Status |
|---|---|---|
| **Requirements Parser** | Extracts entities, relationships, and business rules from documents (IREB-aligned output) | ✅ Built |
| **Business-Key Identifier** | Scores key candidates against DV2.0 heuristics; flags ambiguity for review | ✅ Built |
| **DV2.0 Modeler** | Generates Hubs, Links, and Satellites under DV2.1 rules | ✅ Built |
| **Code Generator** | Emits AutomateDV dbt models — hubs, links, standard/multi-active/effectivity satellites, non-historized links — plus metadata | ✅ Built |
| **Validator** | Checks the model and generated artifacts for DV2.0 compliance | ✅ Built |
| **ADR Author** | Turns the agents' modeling decisions into an explicit, traceable ADR | ✅ Built |
| **Data Contract Agent** | Drafts JSON-Schema source-to-staging contracts + dbt schema tests; flags gaps for human review | ✅ Built |
| **Orchestrator** | Plans the run (entry node) and drives the live human-in-the-loop checkpoint (interrupt / resume) | ✅ Built |

The pipeline self-corrects automatically: a failing validation routes back to the modeler with the
issues as feedback, bounded by a retry cap. On the validated path a human-in-the-loop checkpoint
assembles a categorized review queue and pauses the run (LangGraph `interrupt()`) whenever something
blocks sign-off — a validation error, or a data contract still awaiting an owner. `vault-agent resume`
continues the same run from a persisted SQLite checkpoint once the human decides.

## What you get

- **Speed without sacrificing rigor** — collapse initial DV2.0 modeling from weeks toward hours
- **Reproducible outputs** — reviewed dbt projects in git, never a no-code black box
- **Warehouse-agnostic** — focus on Snowflake & MS Fabric (DACH), but runs on any AutomateDV-supported platform (Snowflake, BigQuery, Databricks, MS SQL Server, PostgreSQL); PostgreSQL for the local demo
- **Knowledge capture** — every modeling decision documented as an ADR
- **Human-in-the-loop sign-off** — the run pauses for owner assignment and approval, then resumes from a checkpoint
- **A force multiplier, not a replacement** — the architect keeps judgment; the agents do the toil

## Quick start

The pipeline runs end-to-end today: a requirements document in; generated AutomateDV/dbt models,
metadata, data contracts, and an ADR out.

```bash
git clone https://github.com/mischa76/vault-agent.git
cd vault-agent
uv sync
cp .env.example .env          # then add your ANTHROPIC_API_KEY

# Run the full pipeline on a demo dataset and write artifacts to ./output
uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

Optionally ground the model against a **declared source schema** (YAML/JSON listing each
source table and its columns) so proposed business keys and satellite attributes are
cross-checked against columns that actually exist (ADR-0004). With a schema supplied,
the run reports `grounding: on`, emits one data contract per source table, and flags any
key/attribute absent from the schema as a non-blocking `W_*_NOT_IN_SOURCE` warning:

```bash
uv run vault-agent run examples/inputs/bank_account_requirements.md \
  --source-schema examples/inputs/bank_source_schema.yml --out output
```

Without `--source-schema`, grounding stays inert and the output is unchanged. To see
grounding bite, drop or rename a column in the schema file and re-run.

This produces dbt models (`output/models/*.sql`), AutomateDV metadata
(`output/metadata/automatedv.yml`), data contracts and their dbt tests (`output/contracts/`), and a
finalized ADR (`output/adrs/`). When the run needs human sign-off (e.g. to assign a data-contract
owner) it pauses at a checkpoint and writes `output/review-queue.md`; resume it once you've decided:

```bash
uv run vault-agent resume --out output --owner "customer=Data Team <data@acme.com>" --accept
```

The `examples/` directory has step-by-step scripts that run each stage in isolation
(`01_simple_requirement.py` … `06_pipeline.py`), plus `07_routing.py`, a deterministic demo of
the self-correcting validation loop that needs **no API key**. The two demo domains
(retail banking and health insurance) are described in [docs/demos/](docs/demos/README.md).

### Run the generated vault (local Postgres)

The pipeline's output is not just plausible SQL — it is **operable**. The
[`demo/bank_postgres/`](demo/bank_postgres/README.md) Durchstich takes the *real* code
generator's AutomateDV/dbt models, loads toy data through a staging layer, and builds a running
Data Vault (two hubs, a link, two standard satellites, and an effectivity satellite) on a local
PostgreSQL 16 — no API key, no Docker required:

```bash
cd demo/bank_postgres
uv sync --extra demo                        # dbt-core + dbt-postgres
uv run python build_vault_models.py         # regenerate raw_vault/*.sql from the generator
DBT_PROFILES_DIR=. uv run dbt deps          # pull AutomateDV
DBT_PROFILES_DIR=. uv run dbt build --full-refresh   # seed + run + test, all green
```

See the [demo runbook](demo/bank_postgres/README.md) for prerequisites and verification.

> The requirements parser, business-key identifier, and modeler are LLM-driven (Claude); the code
> generator, validator, and ADR author are deterministic, so the test suite (`uv run pytest`) runs
> without an API key.

## Methodological foundations

This is not vibes-based modeling. The agents are grounded in established practice:

- **Data Vault 2.1** — Dan Linstedt / DataVaultAlliance (methodology and rules)
- **DSAF** — Roelant Vos, Data Solutions Architecture Framework
- **IREB CPRE** — requirements-engineering conventions for the parsing stage
- **Data Contracts** — Chad Sanderson, Mark Freeman & B.E. Schmidt, *Data Contracts: Developing Production-Grade Pipelines at Scale* (O'Reilly, 2025)

## Tech stack

Python 3.12+ · [uv](https://github.com/astral-sh/uv) · [LangGraph](https://langchain-ai.github.io/langgraph/)
· Anthropic Claude API · [AutomateDV](https://automate-dv.com/) · [dbt Core](https://www.getdbt.com/)
· [LangSmith](https://www.langchain.com/langsmith) · pytest · ruff · mypy (strict)

## Status & roadmap

Actively built in the open. The **core pipeline runs end-to-end on two demo domains** today, via
a CLI, with the methodology rules in code and a self-correcting validation loop.

```
Foundation        repo · architecture · ADRs                                  ✅ done
Core pipeline     requirements parser · business-key id · DV2.0 modeler        ✅ done
Code generation   AutomateDV: hubs · links · sat · ma_sat · eff_sat · nh_link  ✅ done
Quality & docs    validator · ADR author · CLI · 2 demo datasets               ✅ done
Routing           self-correcting validation loop (retry on failure)           ✅ done
Grounding         optional source-schema grounding (ADR-0004)                  ✅ done
Contracts         data contract agent + dbt schema tests                       ✅ done
Orchestration     orchestrator entry node · live HITL (interrupt/resume)       ✅ done
Polish            LangSmith evals · public walkthrough                         🔜 next
```

## Documentation

- [Vision](docs/architecture/0-vision.md)
- [Architecture overview](docs/architecture/1-architecture-overview.md)
- [Multi-agent design](docs/architecture/2-multi-agent-design.md)
- [How requirements become a model (behaviour, assumptions & target)](docs/how-requirements-become-a-model.md)
- [Architecture Decision Records](docs/architecture/adrs/)
- [Automation scope & ambition per layer (ADR-0007)](docs/architecture/adrs/ADR-0007-automation-scope-by-layer.md)
- [Competitive landscape & differentiation](docs/competitive-landscape.md)
- [DV2.0 rules cheatsheet](docs/methodology/dv2-rules-cheatsheet.md)
- [Demo datasets & walkthroughs](docs/demos/README.md)

## About

Built by **Mischa Eismann** ([eismann.consulting](https://eismann.consulting)) — 20+ years in
ICT, a hybrid technical + business profile, and a CDVP² (Certified Data Vault 2.0 Practitioner).
Vault-Agent is a working exploration of where rigorous data-warehouse practice meets agentic AI.

Questions, ideas, or a DV2.0 modernization to discuss? Open an issue or reach out via
[eismann.consulting](https://eismann.consulting).

## License

MIT — see [LICENSE](LICENSE).
