# Vault-Agent – Project Context for Claude

## Mission
Build a multi-agent system that automates Data Vault 2.0 modeling and code generation
from business requirements documents. Target market: Swiss/DACH enterprises with large
DWH landscapes (banks, insurers, pharma, mid-market).

## Author
Mischa Eismann (eismann.consulting). Holds CDVP² (Data Vault 2.0 Practitioner, 2015 –
2.1 refresh in progress) and has 20+ years ICT experience. Hybrid Tech + Business
profile, already builds LLM/agentic prototypes.

## Strategic context
This project is a "lighthouse" – it must serve simultaneously as:
- a skill-build exercise (closes the visible Agentic-AI gap)
- a portfolio asset (CV, pitches for senior architect / lead consultant roles)
- a marketing asset for the eismann.consulting brand
Implication: code quality, documentation quality, and reproducibility all matter.
Public GitHub from W4 onwards.

## Technology stack (locked unless an ADR says otherwise)
- Python 3.12+
- uv for dependency management
- LangGraph for orchestration (state machine, subgraphs, persistence)
- Anthropic Claude API (Sonnet primary, Opus for hard reasoning)
- Anthropic MCP for tool integration
- AutomateDV (OSS dbt package) as the code-gen backend
- dbt Core for transformations (Snowflake + MS Fabric as target platforms, DuckDB for demo)
- LangSmith for tracing/evaluation
- pytest for tests, ruff + mypy for quality

## Methodological foundations (cite when relevant)
- Data Vault 2.1 (Dan Linstedt / DataVaultAlliance) – methodology and rules
- DSAF (Roelant Vos) – Data Solutions Architecture Framework
- IREB CPRE Foundation – Requirements Engineering conventions
- Andrew Jones – Driving Data Quality with Data Contracts (Manning)

## Code conventions
- Type hints everywhere; pydantic for data models; mypy strict
- Each agent in its own file under src/vault_agent/agents/
- Prompts live as .md files in src/vault_agent/prompts/, loaded by the agent
- LangGraph state is a single pydantic model in state.py; agents read/write specific fields
- Tools are MCP-style: typed inputs, typed outputs, idempotent where possible
- Each agent decision the LLM makes that affects the model should produce a draft ADR
  fragment that the ADR Author agent can finalize
- No business logic in graph.py – only orchestration

## What NOT to do
- Don't hard-code DV2.0 rules in agent prompts; put them in src/vault_agent/rules/
- Don't bypass AutomateDV by writing dbt models from scratch
- Don't introduce a new framework (e.g., crewAI, AutoGen) without an ADR
- Don't add UI work until end-to-end pipeline works on at least 2 demo datasets

## Where things live
- Architecture docs and ADRs: docs/architecture/
- Methodology cheatsheets: docs/methodology/
- Demo datasets and walkthroughs: docs/demos/
- Test fixtures: tests/fixtures/
- Example scripts (entry points): examples/
- Eval framework: eval/

## Current milestone (update as we progress)
Core pipeline runs end-to-end (as of 2026-06-11). Built: 6 agents
(requirements_parser, business_key_identifier, dv2_modeler, code_generator, validator,
adr_author) wired into a LangGraph state machine (graph.py) with a self-correcting
validation loop (validation fails → re-model, bounded by MAX_MODELING_ATTEMPTS) and an
ADR branch on success. Code generator emits AutomateDV dbt models for hubs, links,
standard/multi-active/effectivity satellites, and non-historized links, plus metadata.
CLI (`vault-agent run <doc> --out <dir>`) writes models, metadata, and the ADR to disk.
Two demo datasets (bank, health insurance) run through the full pipeline. Tests green
without an API key (LLM calls are injectable/stubbed); ruff + mypy strict clean.

Still stubs: data_contract, orchestrator. Planned: checkpointing + human-in-the-loop
(ADR-0002), transactional-link payload modeling improvements, LangSmith evals.

## References to nearby work
- Learning plan: ../Lernplan_Mapping.xlsx
- Project charter: ../Vault-Agent_Projektkonzept.docx
- Roelant Vos DSAF workshop notes: ../Roelant Vos DSAF WS/
- Data Contracts (Jones, early release): ../data_contracts_early_release.pdf
