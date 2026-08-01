# Vault-Agent — project context for Claude

## Mission
Build a multi-agent system that automates Data Vault 2.0 modeling and code generation from
business requirements documents. Target market: Swiss/DACH enterprises with large DWH landscapes
(banks, insurers, pharma, mid-market).

## Author
Mischa Eismann (eismann.consulting) — CDVP² (Data Vault 2.0 Practitioner, 2015), 20+ years in ICT.

## Technology stack (locked unless an ADR says otherwise)
- Python 3.12+, uv for dependency management
- LangGraph for orchestration (state machine, subgraphs, persistence)
- Anthropic Claude API (Sonnet primary, Opus for hard reasoning); MCP for tool integration
- AutomateDV (OSS dbt package) as the code-gen backend; dbt Core for transformations
- Strategic targets Snowflake + MS Fabric (DACH); any AutomateDV-supported platform works;
  PostgreSQL for the local demo (AutomateDV has no DuckDB support)
- LangSmith for tracing/evaluation, pytest for tests, ruff + mypy strict for quality

## Methodological foundations (cite when relevant)
Data Vault 2.0 (Linstedt/Olschimke) · DSAF (Roelant Vos) · IREB CPRE Foundation ·
Data Contracts (Sanderson, Freeman & Schmidt, O'Reilly 2025) · Karpathy LOOPS.md and LLM Wiki.
Each is mapped critically — adopted / partially / deviated — in `docs/methodology/`. Read the
mapping before citing the source; the deviations are deliberate and argued.

## Code conventions
- Type hints everywhere; pydantic for data models; mypy strict
- Each agent in its own file under `src/vault_agent/agents/`
- Prompts live as `.md` files in `src/vault_agent/prompts/`, loaded by the agent
- LangGraph state is a single pydantic model in `state.py`; agents read/write specific fields
- Tools are MCP-style: typed inputs, typed outputs, idempotent where possible
- No business logic in `graph.py` — only orchestration
- Each LLM decision that affects the model produces material the ADR author can finalize

## What NOT to do
- Don't hard-code DV2.0 rules in agent prompts; put them in `src/vault_agent/rules/`
- Don't bypass AutomateDV by writing dbt models from scratch
- Don't introduce a new framework (crewAI, AutoGen, a wiki server, …) without an ADR
- Don't add UI work until the end-to-end pipeline works on at least 2 demo datasets
- Don't generate Business Vault logic or mart semantics as if authoritative; the agent assists
  and flags those for human ratification only (automation scope per layer: ADR-0007)

## Where things live
- `docs/index.md` — **the catalogue of everything else.** Start there, not by globbing `docs/`
- `docs/log.md` — the chronicle: every closed WP, live measurement and correction, append-only
- `docs/architecture/` — ADRs, WP specs, kick-offs, reviews, spike memos (append-only records)
- `docs/methodology/` — the cheatsheets and the four critical mappings
- `docs/operations/` — the 13-chapter operations manual (gates, flags, exit codes, troubleshooting)
- `tests/fixtures/` — byte-identity baselines · `eval/` — the eval harness · `demo/` — runnable demos

## Invariants

Rules an agent must apply without being told. Format: trigger, action, evidence. The first four
are craft rules that also exist at user scope (`~/.claude/rules/`); they are repeated here so a
fresh clone does not lose them.

- **Verify against the installed thing, not memory.** *Trigger:* you are about to use a macro,
  signature, flag or behaviour of a library (AutomateDV, LangGraph, the Anthropic SDK, dbt).
  *Action:* read the installed package or the live documentation first. *Evidence:* cite what you
  read — file plus signature — in the commit or spec. `automate_dv.nh_link` does not exist; the
  macro is `t_link`, and only a real Postgres build found it (`docs/log.md`, 2026-07-08).

- **Write the guard before the change.** *Trigger:* a change that must leave existing output
  untouched. *Action:* commit the byte-identity fixture or manifest first, then change.
  *Evidence:* the guard fails without your change reverted. Deliberately updating a fixture is
  allowed — in the same commit, with the reason in the message.

- **Audit the traces before paying for another live run.** *Trigger:* a live run failed and you
  want to re-run. *Action:* read `.vault-agent/traces/*.jsonl` and the stored eval results first;
  replay through the deterministic parts at zero cost. *Evidence:* quote tool name, attempt and
  numbers, not a hunch. Three ~$5 runs once found serially what one trace audit held already
  (`docs/log.md`, 2026-07-28).

- **Branch on typed fields, never on message text.** *Trigger:* code needs to react to a flag,
  issue or proposal. *Action:* branch on `FlagKind`/`asset`, `ValidationIssue.code`/`severity`,
  the confidence category. *Evidence:* no regex over a human-readable message anywhere in the
  branch. Substring matching once pruned `customer_address` when `customer` was assigned.

- **The code owns every count, version and threshold.** *Trigger:* you want to state how many
  gates exist, which AutomateDV version is pinned, what a cap is. *Action:* read it from the
  source (`rg "E_[A-Z_]+" src/vault_agent/agents/validator.py`, `rules/dv2_rules.py`). *Evidence:*
  prose that repeats such a value has been wrong twice; docs that must carry one are updated in
  the same commit as the code.

- **Ask the helper in `rules/`; never re-derive its answer.** *Trigger:* you need a hub's staging
  key column, a satellite's feed or payload relations, a role-qualified column, a normalised
  identifier. *Action:* call `canonical_hub_key_column`, `satellite_feed`,
  `satellite_payload_relations`, `role_fk_column`/`role_bk_column`, `normalize_identifier`.
  *Evidence:* three of five call sites once bypassed the first of these and staged a hash from
  the wrong relation — the only defect class here that produced wrong *data* (WP24).

- **Graph order is load-bearing.** *Trigger:* you are tempted to reorder nodes. *Action:* don't.
  `data_contract` runs before `code_generator` because staging reads the contracts; code
  generation runs before the validator because the validator validates generated artifacts; the
  source mapper runs after validation and re-binds staging itself. *Evidence:* the reason is in
  the WP7/WP9 specs, and a reorder breaks silently, not loudly.

- **A gate refuses; a backstop repairs.** *Trigger:* the model produces something wrong.
  *Action:* decide which one you are adding — a deterministic `E_` gate that blocks before
  generation and feeds the re-model loop, or a backstop that repairs and emits telemetry. New
  prompt steering goes through the WP16 registry and `docs/architecture/steering-ledger.md`.
  *Evidence:* validator gates are product and are never ablated; steering and backstops are
  model-compensation and are re-tested per model release.

- **Output that scales with the landscape needs a plan.** *Trigger:* an agent's response grows
  with the number of source tables. *Action:* list-shaped output goes through
  `llm.call_with_truncation_split` with a domain-specific merge; a single coherent artefact
  (the model) has only the budget lever (ADR-0010). *Evidence:* peak-output-against-cap per agent
  is measurable from the traces — measure before raising a number.

- **The test suite runs without an API key.** *Trigger:* you add anything that calls a model.
  *Action:* put it behind an injectable seam and test the deterministic core keylessly. *Evidence:*
  `uv run pytest` is green with no key set. Live measurement is a separate, paid, recorded activity.

- **Records are append-only.** *Trigger:* a new finding contradicts an ADR, spec or log entry.
  *Action:* add a dated entry that says so; never edit the old text. *Evidence:* the correction is
  findable by date, and the original reasoning is still readable.

- **Definition of done.** `uv run pytest`, `uv run ruff check`, and a bare `uv run mypy` — no path
  argument, it overrides `pyproject`'s file list and silently skips `eval/`. Then a `docs/log.md`
  entry. A live-verified claim names its evidence; a keyless-only claim says so.

## Current state

The pipeline runs end-to-end: orchestrator → requirements parser → business keys → data contracts
→ modeler → code generator → validator (bounded re-model loop) → source mapper → HITL checkpoint
→ ADR author. Output is a runnable dbt project (staging + raw vault + scaffolding), data
contracts, a review queue, an HTML report, and a proposed ADR. Brownfield mode (`run --existing`)
extends an existing vault instead of modelling into an empty one. Verified on real PostgreSQL
several times, most recently for brownfield additivity. Details and dates: `docs/log.md`.

## Open items — do not assume these work

- **Scale is verified at ~30 tables of real semantic variety, and unverified above it.**
  `scale_100` does complete and validate, but the synthetic landscape does not scale *information*
  with table count, so the upper cases measure width and repetition tolerance rather than semantic
  scale (`scale-test-findings.md`, candidate #5). `scale_300` has not been run; `emit_dv_model` is
  the one agent that cannot split its output, so its budget is the only lever there.
- **WP30's arm comparison: one repeat each on current code (2026-08-01), and it goes AGAINST the
  charter.** Arm B totals 3x arm A's review items and builds 73% of its links, at 12% lower cost.
  At n=1 that is a direction, not a verdict — the link deficit is the open question. Spec §7.3.
- **WP29's mechanism is live-verified; its correctness is not, and §4 cannot run yet.** The
  checkpoint steers the modeler in a real chain (2026-08-01). But `brownfield_resolution` has no
  `dataset.yml`, no requirements, no scorer dispatch — and `false_merge_rate` matches the golden
  by concept name while the pipeline emits `entity::field` keys, so it would score every correct
  merge as a false one. Fix that before spending anything on §4.
- **WP18 acceptance #1 is unverified** (it costs a live run).

## How this file is maintained

This file is loaded in full on every request; everything below the always-needed layer belongs in
`docs/`. Budget: **200 lines**. A new entry earns a place here only if an agent did the wrong
thing without it — otherwise it is a log entry. At budget, adding one means evicting one.
Procedure, checklists and the lint pass: `.claude/skills/project-docs/SKILL.md`. Rationale and the
verified loading semantics behind this split: `docs/methodology/llm-wiki-mapping.md`.
