<div align="center">

# Vault-Agent

**Agentic AI for Data Vault 2.0 — from business requirements to compliant, contract-backed dbt code.**

A multi-agent system that reads requirements documents and source schemas, then designs a
Data Vault 2.1 model, generates AutomateDV-backed dbt code, and documents every decision it
makes — keeping the rigor of the methodology while removing the repetitive parts.

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
is already in place — when the generated model fails the DV2.0 rule checks it routes back to the
modeler with the issues as feedback, bounded by a retry cap — while checkpointing and
human-in-the-loop gates (per [ADR-0002](docs/architecture/adrs/ADR-0002-orchestration-langgraph.md))
are the next step on the roadmap. The methodology rules live in code (not buried in prompts), code
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
        │   checkpointing · HITL (planned)      │
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
        Targets:  Snowflake  ·  MS Fabric  ·  DuckDB (demo)
                 Observability:  LangSmith traces + evals
```

## The agents

Eight specialized agents, orchestrated in LangGraph — **six built, two planned**:

| Agent | Responsibility | Status |
|---|---|---|
| **Requirements Parser** | Extracts entities, relationships, and business rules from documents (IREB-aligned output) | ✅ Built |
| **Business-Key Identifier** | Scores key candidates against DV2.0 heuristics; flags ambiguity for review | ✅ Built |
| **DV2.0 Modeler** | Generates Hubs, Links, and Satellites under DV2.1 rules | ✅ Built |
| **Code Generator** | Emits AutomateDV dbt models — hubs, links, standard/multi-active/effectivity satellites, non-historized links — plus metadata | ✅ Built |
| **Validator** | Checks the model and generated artifacts for DV2.0 compliance | ✅ Built |
| **ADR Author** | Turns the agents' modeling decisions into an explicit, traceable ADR | ✅ Built |
| **Data Contract Agent** | Generates source-to-staging data contracts | 🔜 Planned |
| **Orchestrator** | Adds checkpointing and human-in-the-loop pauses on top of the pipeline | 🔜 Planned |

Today the pipeline self-corrects automatically: a failing validation routes back to the modeler
with the issues as feedback, bounded by a retry cap. The planned orchestrator will add
human-in-the-loop pauses — e.g. when business-key candidates score within 10% of each other, when
the validator finds rule violations the modeler can't resolve, or when a generated artifact would
overwrite user-modified files.

## What you get

- **Speed without sacrificing rigor** — collapse initial DV2.0 modeling from weeks toward hours
- **Reproducible outputs** — reviewed dbt projects in git, never a no-code black box
- **Warehouse-agnostic** — Snowflake, MS Fabric, and DuckDB for demos
- **Knowledge capture** — every modeling decision documented as an ADR
- **A force multiplier, not a replacement** — the architect keeps judgment; the agents do the toil

## Quick start

The pipeline runs end-to-end today: a requirements document in, generated AutomateDV/dbt models,
metadata, and an ADR out.

```bash
git clone https://github.com/mischa76/vault-agent.git
cd vault-agent
uv sync
cp .env.example .env          # then add your ANTHROPIC_API_KEY

# Run the full pipeline on a demo dataset and write artifacts to ./output
uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

This produces dbt models (`output/models/*.sql`), AutomateDV metadata
(`output/metadata/automatedv.yml`), and a finalized ADR (`output/adrs/`).

The `examples/` directory has step-by-step scripts that run each stage in isolation
(`01_simple_requirement.py` … `06_pipeline.py`), plus `07_routing.py`, a deterministic demo of
the self-correcting validation loop that needs **no API key**. The two demo domains
(retail banking and health insurance) are described in [docs/demos/](docs/demos/README.md).

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
Contracts         data contract agent (source-to-staging)                      🔜 next
Orchestration     checkpointing · human-in-the-loop gates                      🔜 next
Polish            LangSmith evals · public walkthrough                         🔜 later
```

## Documentation

- [Vision](docs/architecture/0-vision.md)
- [Architecture overview](docs/architecture/1-architecture-overview.md)
- [Multi-agent design](docs/architecture/2-multi-agent-design.md)
- [Architecture Decision Records](docs/architecture/adrs/)
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
