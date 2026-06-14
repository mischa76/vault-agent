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
- Chad Sanderson, Mark Freeman & B.E. Schmidt – Data Contracts: Developing Production-Grade Pipelines at Scale (O'Reilly, 2025)

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

DV2.0 modeling rules are now encoded (as of 2026-06-13) per the Linstedt/Olschimke
canon (dv2-modeling-rules-spec.md), split into [ENFORCE] rules (validator gates) and
[GUIDE] rules (modeler prompt). The validator has 10 independent gates with E_/W_ codes
enforcing driving keys, grain, attribute overlap, wide-satellite splits, and BK
collision; rules/dv2_rules.py holds the UoW/driving-key/splitting/collision guidance,
SATELLITE_SPLIT_AXES, and SAT_WIDE_ATTRIBUTE_THRESHOLD. State carries Link.driving_key
(required for effectivity), Link.unit_of_work, and Satellite.split_rationale for the ADR
trail, which the adr_author surfaces when present.

Architecture-review remediation worked end-to-end (as of 2026-06-13, see
docs/architecture/review-2026-06-remediation-spec.md): the effectivity satellite now
applies the link's declared driving_key (src_dfk); config is lazy via get_settings() with
a valid heavy_model; the modeling retry cap reads an explicit state.modeling_attempts (not
the audit log); the adr_author is the sole writer of state.adrs (no draft-fragment
accumulation); the code generator flags UPPER_SNAKE column-name collisions. Requirements
parser now reads .md/.txt/.pdf/.docx (pypdf + python-docx). source_schemas is now a typed
list[SourceTable] consumed for grounding (ADR-0004): validator warns
W_BK_NOT_IN_SOURCE/W_ATTR_NOT_IN_SOURCE and the modeler/business-key prompts are steered to
real columns when a schema is declared — fully inert (no regression) when it is empty
(grounding helpers in src/vault_agent/grounding.py).

The data_contract agent is now implemented (as of 2026-06-14, ADR-0005) and wired into
the pipeline after business_key_identifier (contracts describe source-to-staging assets,
so they depend only on requirements/business_keys/source_schemas, not the DV model, and
are unaffected by the validation re-model loop). It drafts a JSON-Schema-based contract
per asset (one per SourceTable when a schema is declared, else one per business entity)
into state.artifacts.contracts, plus dbt schema-tests into state.artifacts.dbt_tests; the
CLI writes both under output/contracts/. Typed contract model in
src/vault_agent/models/contract.py (DataContract with spec-version/schema aliases,
hard/soft failure modes, union/enum types). Split mirrors the other agents: deterministic
core (asset/field selection, business-key→primaryKey/not-null, failure modes, placeholder
owner, dbt-test emission, serialization) is unit-tested without a key; an injectable
ContractEnricher (Anthropic forced tool-use) supplies doc/descriptions/type-inference/
semantics. Gaps are flagged for human review (placeholder owner, missing source schema,
undetermined type), never guessed.

The orchestrator is now implemented (as of 2026-06-14, ADR-0006) and is the graph entry
node (START → orchestrator → requirements_parser → …), matching the multi-agent design
topology. It is deterministic (no LLM): (1) it validates inputs and writes a typed
ExecutionPlan (state.plan: planned stages, declared inputs, grounding on/off) for
observability; (2) it owns the human-in-the-loop checkpoint as a deterministic review
queue — assemble_review_queue(state) derives a categorized HumanReviewQueue (validation
errors/warnings, contracts with placeholder owners, advisory review flags), with
requires_signoff true when a validation error or unassigned contract owner blocks
agreement. The CLI prints the checkpoint (blocking-first) and write_outputs writes
review-queue.md. Per ADR-0006 this is the "what to review" half; live pause/resume
(LangGraph interrupt() + checkpointer + CLI resume) is the deferred "how to pause" half.
ContractOwner.PLACEHOLDER_NAME is the single source for the placeholder-owner marker.

Live human-in-the-loop interrupt/resume now works (as of 2026-06-15, ADR-0006 second half).
A human_checkpoint node sits on the validated path (validator --pass--> human_checkpoint -->
adr_author): it assembles the review queue and, when requires_signoff (a validation error or
unassigned contract owner), calls LangGraph interrupt() to pause — interrupt() is the node's
first statement since the node re-executes from the top on resume. The graph is compiled with
a persistent AsyncSqliteSaver (langgraph-checkpoint-sqlite) keyed by a per-run thread_id under
<out>/.vault-agent/. CLI: `vault-agent run` detects the interrupt, writes artifacts-so-far +
pending.json, and prints resume instructions; `vault-agent resume --owner "asset=Name <email>"
[--accept]` continues the same thread via Command(resume=...). apply_human_decision writes
owners onto the contracts and prunes resolved owner flags, then the ADR author finalizes. The
checkpointer serde is configured with an allow-list of the state models (cli._checkpoint_serde)
to avoid LangGraph's "unregistered type" deprecation warning. Tested without an API key via
MemorySaver (graph interrupt/resume) + pure-function unit tests; AsyncSqliteSaver verified for
cross-connection resume.

No agents remain as stubs; the HITL loop is closed. Planned: transactional-link payload
modeling improvements, LangSmith evals, and (when a UI lands) an interactive resume prompt.

## References to nearby work
- Learning plan: ../Lernplan_Mapping.xlsx
- Project charter: ../Vault-Agent_Projektkonzept.docx
- Roelant Vos DSAF workshop notes: ../Roelant Vos DSAF WS/
- Data Contracts (Jones, early release): ../data_contracts_early_release.pdf
