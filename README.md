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
well-defined step, coordinated by a LangGraph supervisor with checkpointing and human-in-the-loop
gates. The methodology rules live in code (not buried in prompts), code generation goes through
the established AutomateDV dbt package rather than hand-written SQL, and every modeling decision
the agents make is captured as an Architecture Decision Record — so the *reasoning* survives, not
just the output.

```
  Requirements (PDF / DOCX / MD)  +  Source schemas (SQL / DDL)
                          │
                          ▼
        ┌──────────────────────────────────────┐
        │   LangGraph supervisor + subgraphs    │
        │   (checkpointed · human-in-the-loop)  │
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

Eight specialized agents, orchestrated in LangGraph:

| Agent | Responsibility |
|---|---|
| **Requirements Parser** | Extracts entities, relationships, and business rules from documents (IREB-aligned output) |
| **Business-Key Identifier** | Scores key candidates against DV2.0 heuristics; flags ambiguity for review |
| **DV2.0 Modeler** | Generates Hubs, Links, and Satellites under DV2.1 rules |
| **Code Generator** | Emits AutomateDV-compatible YAML + dbt models |
| **Data Contract Agent** | Generates source-to-staging data contracts |
| **Validator** | Checks generated artifacts for DV2.0 compliance |
| **ADR Author** | Turns the agents' implicit decisions into explicit ADRs |
| **Orchestrator** | Plans agent order and handles human-in-the-loop pauses |

The orchestrator stops for a human when business-key candidates score within 10% of each other,
when the validator finds rule violations the modeler can't resolve, or when a generated artifact
would overwrite user-modified files.

## What you get

- **Speed without sacrificing rigor** — collapse initial DV2.0 modeling from weeks toward hours
- **Reproducible outputs** — reviewed dbt projects in git, never a no-code black box
- **Warehouse-agnostic** — Snowflake, MS Fabric, and DuckDB for demos
- **Knowledge capture** — every modeling decision documented as an ADR
- **A force multiplier, not a replacement** — the architect keeps judgment; the agents do the toil

## Quick start

> The end-to-end pipeline lands at the first implementation milestone. The commands below are
> the intended entry point.

```bash
git clone https://github.com/mischa76/vault-agent.git
cd vault-agent
uv sync
cp .env.example .env          # then add your ANTHROPIC_API_KEY
uv run vault-agent --help     # CLI entry point
uv run python examples/01_simple_requirement.py
```

## Methodological foundations

This is not vibes-based modeling. The agents are grounded in established practice:

- **Data Vault 2.1** — Dan Linstedt / DataVaultAlliance (methodology and rules)
- **DSAF** — Roelant Vos, Data Solutions Architecture Framework
- **IREB CPRE** — requirements-engineering conventions for the parsing stage
- **Data Contracts** — Andrew Jones, *Driving Data Quality with Data Contracts* (Manning)

## Tech stack

Python 3.12+ · [uv](https://github.com/astral-sh/uv) · [LangGraph](https://langchain-ai.github.io/langgraph/)
· Anthropic Claude API · [AutomateDV](https://automate-dv.com/) · [dbt Core](https://www.getdbt.com/)
· [LangSmith](https://www.langchain.com/langsmith) · pytest · ruff · mypy (strict)

## Status & roadmap

Actively built in the open over a 12-week arc. Currently **W1 — Foundation**: repo skeleton,
architecture docs, ADRs, and the requirements-parser proof of concept.

```
W1   Foundation        repo · architecture · ADRs · requirements-parser PoC   ◀ you are here
W2+  Core pipeline     business-key id · DV2.0 modeler · AutomateDV codegen
     Contracts & QA    data contracts · validator · ADR author
     Demos             end-to-end on ≥2 datasets (bank + second domain)
     Polish            evals · docs · public walkthrough
```

## Documentation

- [Vision](docs/architecture/0-vision.md)
- [Architecture overview](docs/architecture/1-architecture-overview.md)
- [Multi-agent design](docs/architecture/2-multi-agent-design.md)
- [Architecture Decision Records](docs/architecture/adrs/)
- [DV2.0 rules cheatsheet](docs/methodology/dv2-rules-cheatsheet.md)

## About

Built by **Mischa Eismann** ([eismann.consulting](https://eismann.consulting)) — 20+ years in
ICT, a hybrid technical + business profile, and a CDVP² (Certified Data Vault 2.0 Practitioner).
Vault-Agent is a working exploration of where rigorous data-warehouse practice meets agentic AI.

Questions, ideas, or a DV2.0 modernization to discuss? Open an issue or reach out via
[eismann.consulting](https://eismann.consulting).

## License

MIT — see [LICENSE](LICENSE).
