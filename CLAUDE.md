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
- `~/.claude/projects/<path-slug>/memory/` — **not a storage location.** Machine-local and keyed
  by checkout path, so copying the project to a second path silently starts a second, empty store
  — which is what the WSL→`/mnt/c` move for Cowork's tools did here. Durable facts go to
  `docs/log.md` (SKILL step 5). Conventions: `~/.claude/rules/wissensbasis.md`

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
  entry. A live-verified claim names its evidence and says *which* live: a paid LLM run verifies
  modelling, a keyless `dbt build` verifies the warehouse output; a keyless-only claim says so.
  "No dbt build on either line" once erased months of Postgres builds (`docs/log.md`, 2026-09-12).

## Current state

The pipeline runs end-to-end: orchestrator → requirements parser → business keys → data contracts
→ entity resolver + link proposer → resolution checkpoint → modeler → code generator → validator
(bounded re-model loop) → source mapper → HITL checkpoint → ADR author. Output is a runnable dbt project (staging + raw vault + scaffolding), data
contracts, a review queue, an HTML report, and a proposed ADR. Brownfield mode (`run --existing`)
extends an existing vault instead of modelling into an empty one. Verified on real PostgreSQL
several times, most recently for composite keys (2026-10-05). The five-step AdventureWorks chain
(person → sales) ran all-green seven times between 2026-10-05 and 2026-10-09. WP29 §4 (entity-resolution safety) is
met: `false_merge_rate` 1.000 over 5 clean repeats, zero blinded merges (2026-08-08; trap 5 is
blinded-untestable by design). Details and dates: `docs/log.md`.

## Open items — do not assume these work

- **Scale is verified at ~30 tables of real semantic variety, and unverified above it.**
  `scale_100` does complete and validate, but the synthetic landscape does not scale *information*
  with table count, so the upper cases measure width and repetition tolerance rather than semantic
  scale (`scale-test-findings.md`, candidate #5). `scale_300` has not been run; `emit_dv_model` is
  the one agent that cannot split its output, so its budget is the only lever there.
- **The chain is all-green once** (2026-10-05, `20261004T140130528908Z`): all five steps
  `validation_gate` 1.0, WP34 §6's four clauses held (22 cross-domain links against arm A's 16),
  review 353 items / 135 decisions. What made sales and production red on 2026-09-17 and
  2026-10-04 is closed keyless and confirmed live by the loop itself: hash-key collisions (WP44 —
  the remedy's drop was followed in attempt 2, twice), composite business keys (WP45 — the modeler
  typed three hubs), a composite foreign key read per component and the satellite key gate's remedy
  (WP46 — followed on `WorkOrderRouting`, re-parented onto `hub_work_order`). Per-chain numbers and
  history: `docs/log.md` 2026-09-15 → 2026-10-05. **One chain is a shape, not a distribution:** the
  modeler's choices varied across the three chains (cart item as hub or as link; a
  `SalesOrderDetail` satellite built or not), so a class absent in one run is not gone — the
  two-hubs-on-one-source-entity defect appeared inside attempts and was remedied, not fixed; WP46's
  component translation has Postgres evidence but no live case yet. **The arm comparison is a tie
  on decisions** (2026-10-05: arm A 134, arm B 135/148) and arm A is far cheaper to read (21
  disclosures against 218–230); arm B's distinguishing value is brownfield additivity, not less
  attention — do not claim the latter (`docs/log.md` 2026-10-05, WP34 §12). **`source_schemas` means
  „this increment's tables"** to the contract agent, the proposer and the modeler's grounding: handing
  a step the whole catalogue (the `_cumulative` eval case) re-drafts every earlier contract and
  re-proposes every earlier key (193 owners, 227 calls, 9.36 USD) — a binding-only catalogue needs a
  typed split first. **A red step skips the mapper**, and the mapper's re-bind is where freely named
  links bind by offer; an inherited error therefore also inflates `source_binding`. **The repair memory
  keyed hubs by name** until WP49 (2026-10-06) keyed them by shape too — the third chain's step 5 had
  gone red on a retired duplicate re-emitted under a new name; the fourth chain produced no rename.
  **The two-hubs-on-one-person defect was the standing red class** (fourth chain, 2026-10-06, step 5:
  `hub_sales_person` beside `hub_employee`, `E_LINK_KEY_WRONG_COLUMN` refusing correctly). **WP50
  (2026-10-06) gives that gate a remedy with memory** on the ratified key's evidence; the shape has
  not recurred, so WP50 is unmeasured live. **The memory made chains green:** re-emitted retired hubs
  were dropped — on the sixth chain under a new name (WP49's shape retirement, live). **WP51 moves a
  dropped hub's payload to its kept twin** (live on the self-link branch); WP52 makes the chain's gate
  and health the minimum over steps and `extension_conflict` advisory (live). Eleven normal chains:
  red/green/red/red, five green, red, green — the tenth's step 3 on WP54's gate after attempt 3
  regressed: a retry was a new draft — **WP57 (2026-10-09) carries the previous model** with a
  repair line; on the eleventh chain every retry kept 100 % of what no issue named. WP58 reads
  `hub:role` participations (no live case yet). **WP34 §6's review clause is a distribution since
  WP53 (2026-10-07)**: the one-sided 95 % prediction bound over the recorded chains before the judged
  one (`eval/wp34_check.py`); the sixth chain's 156 still fails it, the seventh to eleventh held
  (127, 126, 143, 137, 136), the twelfth is judged against 155.1; a completed chain enters the record
  in its docs commit. **A resumed chain's chain-level file is wrong before 2026-10-07**; read the step
  files. **The eighth chain lost two tables' payload** (`TransactionHistory`, `PurchaseOrderDetail`,
  no satellite read them) — **WP54 (2026-10-07) refuses that** (`E_HUB_PAYLOAD_UNREAD`); live on the
  ninth to eleventh chains, followed within the attempts except the tenth's step 3.
- **WP18 acceptance #1 is unverified** (it costs a live run).
- **The Databricks target is keyless-only.** `--target-platform databricks` (WP35, 2026-09-11)
  changes seed types and the README; no workspace build has ever run. Its extra `demo-databricks`
  (dbt-core 1.11) **conflicts with `demo`** (dbt-core 1.9, the line verified on Postgres since
  2026-06-23) — `uv sync` installs one or the other, never both (`tool.uv.conflicts`, 2026-09-12).

## How this file is maintained

This file is loaded in full on every request; everything below the always-needed layer belongs in
`docs/`. Budget: **250 lines** (200 until 2026-10-09; raised by the owner so that condensing stops costing knowledge). A new entry earns a place here only if an agent did the wrong
thing without it — otherwise it is a log entry. At budget, adding one means evicting one.
Procedure, checklists and the lint pass: `.claude/skills/project-docs/SKILL.md`. Rationale and the
verified loading semantics behind this split: `docs/methodology/llm-wiki-mapping.md`.
