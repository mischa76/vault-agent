# Vault-Agent – Project Context for Claude

## Mission
Build a multi-agent system that automates Data Vault 2.0 modeling and code generation
from business requirements documents. Target market: Swiss/DACH enterprises with large
DWH landscapes (banks, insurers, pharma, mid-market).

## Author
Mischa Eismann (eismann.consulting) — CDVP² (Data Vault 2.0 Practitioner, 2015; 2.1 refresh in
progress), 20+ years in ICT.

## Technology stack (locked unless an ADR says otherwise)
- Python 3.12+
- uv for dependency management
- LangGraph for orchestration (state machine, subgraphs, persistence)
- Anthropic Claude API (Sonnet primary, Opus for hard reasoning)
- Anthropic MCP for tool integration
- AutomateDV (OSS dbt package) as the code-gen backend
- dbt Core for transformations; strategic targets Snowflake + MS Fabric (DACH), but any
  AutomateDV-supported platform works (Snowflake, BigQuery, Databricks, MS SQL Server, PostgreSQL);
  PostgreSQL for the local demo (AutomateDV has no DuckDB support)
- LangSmith for tracing/evaluation
- pytest for tests, ruff + mypy for quality

## Methodological foundations (cite when relevant)
- Data Vault 2.1 (Dan Linstedt / DataVaultAlliance) – methodology and rules
- DSAF (Roelant Vos) – Data Solutions Architecture Framework: a pragmatic architecture lens
  (influence, not an implemented/selectable mode). Adopted ideas and the ADR-gated Vos
  alternatives are critically mapped in docs/methodology/dsaf-mapping.md
- IREB CPRE Foundation – Requirements Engineering conventions
- Chad Sanderson, Mark Freeman & B.E. Schmidt – Data Contracts: Developing Production-Grade Pipelines at Scale (O'Reilly, 2025)

## Code conventions
- Type hints everywhere; pydantic for data models; mypy strict
- Each agent in its own file under src/vault_agent/agents/
- Prompts live as .md files in src/vault_agent/prompts/, loaded by the agent
- LangGraph state is a single pydantic model in state.py; agents read/write specific fields
- Tools are MCP-style: typed inputs, typed outputs, idempotent where possible (the empty tools/
  package was removed 2026-07-08; the directory is reintroduced when the first tool lands)
- Each agent decision the LLM makes that affects the model should produce a draft ADR
  fragment that the ADR Author agent can finalize
- No business logic in graph.py – only orchestration

## What NOT to do
- Don't hard-code DV2.0 rules in agent prompts; put them in src/vault_agent/rules/
- Don't bypass AutomateDV by writing dbt models from scratch
- Don't introduce a new framework (e.g., crewAI, AutoGen) without an ADR
- Don't add UI work until end-to-end pipeline works on at least 2 demo datasets
- Don't generate Business Vault business logic or mart semantics as if authoritative; the agent
  assists and flags those for human ratification only (automation scope per layer: ADR-0007)

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
[GUIDE] rules (modeler prompt). The validator has independent gates with E_/W_ codes (28 as of
2026-07-08 / WP7; may grow — count the codes in validator.py, don't trust prose)
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
unassigned contract owner), calls LangGraph interrupt() to pause — everything before
interrupt() must stay pure/idempotent because the node re-executes from the top on resume
(assemble_review_queue is pure). The graph is compiled with
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

The generated models now run end-to-end on a real warehouse (as of 2026-06-23,
docs/architecture/poc-end-to-end-dbt-spec.md): demo/bank_postgres/ is a runnable end-to-end PoC
that feeds a fixed bank DVModel through the *real* CodeGeneratorAgent (build_vault_models.py,
no API key) and builds the output on a native local PostgreSQL 16 via dbt + AutomateDV 0.11.4.
`dbt build --full-refresh` is green for two hubs, a standard link, two standard satellites and
an effectivity satellite, all populated (verified). The staging layer (stg_* hash-key/hashdiff
models) is hand-authored — the generator does not yet emit it (the biggest gap to a fully
runnable project; see the demo README findings). Postgres casing works by keeping every
identifier unquoted (seeds quote_columns=false) so UPPER_SNAKE folds consistently.
dbt deps live in the `demo` optional-dependency extra (uv sync --extra demo).

Incremental eff_sat fixed (as of 2026-06-23, docs/architecture/eff-sat-incremental-fix-spec.md):
src_eff is now decoupled from src_start_date — the generator sets it to a dedicated
EFFECTIVITY_APPLIED_COLUMN ("APPLIED_DTS", in rules/dv2_rules.py), which staging derives from
EFFECTIVE_FROM. That clears the Postgres "column ... specified more than once" error, so the
incremental eff_sat run is green and idempotent. The generated eff_sat also emits
config(is_auto_end_dating=true) — AutomateDV's auto end-dating is opt-in (default false), and
closing superseded relationships is the defining behaviour of an effectivity satellite.
End-dating is demonstrated via a two-phase snapshot load (demo README → "Phase B2"): after the
transfer batch, ACC-503's first owner row is closed to 2026-04-01 and the new owner stays open
(verified). Test pins: test_code_generator asserts src_eff=="APPLIED_DTS" (≠ src_start_date) and
is_auto_end_dating=true.

Source-schema input producer landed (as of 2026-06-24, docs/architecture/source-schema-input-spec.md):
the declared-but-unfed ADR-0004 grounding now has a producer. `vault-agent run --source-schema
<file.yml/json>` (or -s) loads a declared schema (src/vault_agent/source_schema.py: load_source_schemas
— accepts a top-level `source_schemas:` key or a bare list; empty/null doc → [] = inert; malformed
entry → clear attributable ValueError naming file + problem) into state.source_schemas, activating the
existing consumers: validator W_BK_NOT_IN_SOURCE/W_ATTR_NOT_IN_SOURCE warnings, modeler/business-key
prompt steering, and one data contract per source table. The run summary prints `grounding: on
(N source table(s))` / `off`. Example schema: examples/inputs/bank_source_schema.yml (the bank raw_*
business columns). Fully inert without the flag (byte-for-byte regression guard); resume needs no flag
(persisted in the checkpoint). Phase 2/3 (source-dialect naming + business↔source mapping, staging
generator, DDL/DB introspection) remain out of scope.

Reality-test remediation batch 1 landed (as of 2026-06-25,
docs/architecture/reality-test-remediation-spec.md), both deterministic (no LLM): (#2) a new
validator gate W_SAT_MAYBE_EFFECTIVITY — a heuristic *warning* (never an error) when a standard
satellite hangs off a link and carries a from/to date pair (likely a mis-modelled effectivity sat).
The from/to hint tokens (EFFECTIVITY_FROM_TOKENS/EFFECTIVITY_TO_TOKENS) and the matching helper
effectivity_date_pair() are the single source of truth in rules/dv2_rules.py; the modeler prompt
gains a [GUIDE] line steering active-period relationships to sat_type=effectivity with the link's
driving key. (#3) Review-queue aggregation — ReviewItem.group + aggregate_review_flags() collapse
repetitive advisory flags (>AGGREGATE_THRESHOLD=3 per group: undetermined-type, no-source-schema)
into one summarised line, shared by both renderers (orchestrator.render_review_queue_md and
cli._print_checkpoint); blocking items and validation warnings stay individual and ordered first,
the aggregated advisory block stays last. Aggregation is presentation-only: requires_signoff and the
review_items count are unchanged (count reflects underlying items, not the collapsed display).
Verified live on the messy grounded run (examples/inputs/messy_insurance_*): the 38 undetermined-type
flags collapse to one line while the 5 owner items + 8 substantive warnings surface on top.
The changes are validator/orchestrator/prompt only — they do not touch the code generator, and the
bank Postgres end-to-end PoC was re-verified green on 2026-06-25 (regenerated models byte-identical;
`dbt build --full-refresh` PASS=29; Phase B2 eff_sat end-dating closes ACC-503's first owner and
leaves the new owner open, idempotent on re-run) as a no-regression guard.

Hardening batch P1+P2 landed (as of 2026-07-06, see PROJECT_REVIEW_2026-07-06.md). (P1) The
stringly-typed state.errors channel is replaced by typed state.flags: list[PipelineFlag]
(agent, message, severity error/advisory, kind, asset) with FlagKind constants in state.py;
all producers use state.flag(...), and every consumer (review-queue classification/aggregation
via REVIEW_FLAG_GROUPS keyed by kind, owner-flag dedup, collapsed-line samples via
ReviewItem.asset) branches on kind/asset — never on message text. The former substring regexes
(_classify_review_flag, _SAMPLE_PATTERNS, _OWNER_FLAG_MARKER) are gone. apply_human_decision
now prunes owner flags by exact asset match (fixes the latent bug where assigning `customer`
also pruned `customer_address`). Severity is informational only — requires_signoff semantics
are unchanged (validation errors + unassigned owners block). (P2) All four Anthropic extractor
classes delegate to a shared ForcedToolCaller (src/vault_agent/llm.py): forced single-tool
call, stop_reason=="max_tokens" raises LLMCallError instead of silently returning an empty
payload (a truncated modeler response no longer burns a retry as E_NO_HUBS), missing tool
block raises, transient failures (408/429/5xx/529 + connection/timeout) retry 3× with
exponential backoff (2s/4s/8s), non-retryable 4xx propagate. Client and sleep are injectable;
tests/test_llm.py covers all paths keyless. 158 tests green, ruff clean, mypy strict clean.
Note: docs written before 2026-07-06 that mention `state.errors` describe the old shape.

The staging generator landed (as of 2026-07-06, P3 from PROJECT_REVIEW_2026-07-06.md): the
output is now a runnable dbt project, closing the spec-§9 "biggest single gap". A new
deterministic module (src/vault_agent/agents/staging_generator.py, called by the
CodeGeneratorAgent, lazily to keep the dependency one-directional) derives one
automate_dv.stage model per staging source from the DVModel: hub HKs from business keys,
link HKs as multi-column hashes in connected_hubs order, one hashdiff per standard/ma
satellite (name = base+_HASHDIFF), and the eff_sat parent's dedicated APPLIED_DTS derived
column (rules.EFFECTIVITY_APPLIED_COLUMN) — the generated stg_account_customer is
semantically identical to the demo's hand-authored, Postgres-verified one. Source binding:
a declared source table (ADR-0004) matching the construct base (or raw_<base>) is used
verbatim; otherwise the binding is inferred as rules.RAW_SOURCE_PREFIX+base and flagged
(FlagKind.SOURCE_BINDING, advisory, aggregatable in the review queue) — named, never
silently guessed. Artifacts gain staging_models and scaffolding (dbt_project.yml with
staging-view/raw-vault-incremental defaults and quote_columns=false seeds, packages.yml
pinned to rules.AUTOMATE_DV_VERSION=0.11.4, a documented models/staging/sources.yml
describing the expected raw interface incl. expected columns, README.md with run
instructions); write_outputs writes models/raw_vault/ + models/staging/ + scaffolding at
the output root. The bank demo keeps its hand-authored staging (two-phase load_batch demo
filter); its guardrail test now also asserts the generated staging mirrors it. Deferred:
ma_sat staging grain (spec §9), switching sources.yml from documentation to bound source()
references, generated seeds/column types. 169 tests green, ruff clean, mypy strict clean.
Hardness-tested end-to-end in a clean environment (2026-07-07): a fresh generator output
(fixed bank DVModel → CodeGeneratorAgent → cli.write_outputs, zero hand-written SQL) built
green against a real PostgreSQL with only the README-documented user inputs added (seeds +
profiles.yml): `dbt deps` (AutomateDV 0.11.4) → `dbt seed` → `dbt build --full-refresh`
PASS=12; incremental re-run idempotent; two-phase snapshot load closes ACC-503's superseded
ownership to the successor's business date (2026-04-01) via the generated staging's
APPLIED_DTS — the generated staging behaves exactly like the demo's hand-authored one.
Seed type inference handled timestamps without declared column_types.

Typed ValidationIssue landed (as of 2026-07-07, WP4 of backlog-2026-07,
docs/architecture/backlog-2026-07/wp4-typed-validation-issue-spec.md):
ValidationReport.issues is now list[ValidationIssue] (pydantic, in state.py: severity
Literal["error","warning"], stable machine code, construct, presentation-only message)
instead of list[dict[str, Any]]. The validator's _issue helper constructs the model, the
orchestrator's assemble_review_queue reads attributes instead of defensive .get() parsing
(fallbacks unchanged: empty code renders as "issue", empty construct as "model"), and the
modeler's retry feedback serialises via issue.model_dump() (payload content unchanged).
Pure refactor: same codes/severities/messages, rendered review queue byte-identical for
the existing fixtures. The field name "construct" (DV term of art) shadows the deprecated
BaseModel.construct classmethod; that single definition-time pydantic warning is
suppressed in state.py with a matching targeted mypy ignore. state.decisions stays an
untyped audit log by design. 169 tests green, ruff clean, mypy strict clean.

The ADR author is remediated (as of 2026-07-07, WP2:
docs/architecture/backlog-2026-07/wp2-adr-author-spec.md). The generated model ADR is now a
per-output artifact: always ADR-0001 within its output directory, deterministic and idempotent
(same state in → byte-identical ADR out); repo-level ADR numbering happens only when a human
accepts the proposal and moves it into docs/architecture/adrs/. The repo-layout coupling is
gone (_DEFAULT_ADR_DIR/_next_adr_number/adr_dir removed — the old scheme resolved
parents[3] into site-packages when installed as a wheel and made numbers depend on the repo's
ADR directory). The stale "specialised types … not yet generated" caveat (false since the
nh_link/ma_sat/eff_sat templates landed) is replaced by a flag-derived one: constructs the
code generator actually skipped carry FlagKind.GENERATION_GAP flags (matched on kind/asset,
never message text; adr_author runs after code_generator on the validated path, so the flags
are present), and the ADR lists exactly those as "N construct(s) could not be generated and
are flagged for human review: …" — generated non-standard types get no caveat. The References
section now counts raw-vault and staging models separately. 169 tests green, ruff clean,
mypy strict clean.

Four new validator gates landed (as of 2026-07-08, WP1 of backlog-2026-07,
docs/architecture/backlog-2026-07/wp1-validator-gates-spec.md), all deterministic and
reusing the existing rules helpers (effectivity_date_pair, normalize_identifier — no
re-implemented token/normalisation logic). (1) E_EFFSAT_DATE_ORDER: a 2-attribute
effectivity satellite whose date pair is recognisably reversed (the generator reads
attributes[0]/[1] positionally as start/end) is an error; unclassifiable tokens only warn
(W_EFFSAT_DATE_ORDER_UNVERIFIED — a heuristic non-match never hard-fails, same reasoning
as W_SAT_MAYBE_EFFECTIVITY). (2) E_SAT_DUP_ATTR: two satellite attributes (or an attribute
and a child_dependent_key label — one column namespace) normalising to the same identifier
would emit a duplicate payload column Postgres rejects; blocking before generation, the
generator's _collision_warnings stays as defense in depth. (3) E_HUB_HK_COLLISION: hubs
sharing a normalised source_entity with differing business keys would derive the same
X_HK column and staging model (the staging dedup then silently binds one hub's HK to the
other's BK). (4) E_DUP_HUB: same BK and same source entity on >= 2 hubs is the same concept
modelled twice (complements W_BK_COLLISION_RISK, which covers differing sources); identical
hubs trip only E_DUP_HUB, never gate 3 (same-BK groups are excluded by construction —
pinned by a test). Consistency fix: the code generator now rejects effectivity satellites
with != 2 attributes (was >= 2, silently dropping payload beyond the first two), flagged as
FlagKind.GENERATION_GAP; DV_MODELING_RULES gains a [GUIDE] line steering the modeler to
exactly two date attributes in (start, end) order. Validator code count is 27 (docstring
updated; the code stays the source of truth; 28 since WP7's W_MASAT_SHARED_GRAIN). 179
tests green, ruff clean, mypy strict clean; bank demo guardrails untouched.

WP3 LLM cost & robustness landed (as of 2026-07-08,
docs/architecture/backlog-2026-07/wp3-llm-cost-spec.md), three token-economy fixes.
(1) Prompt caching: ForcedToolCaller.call now sends the system prompt as a
cache-controlled block — system=[{"type": "text", "text": ..., "cache_control":
{"type": "ephemeral"}}] — verified against the live Messages API docs. One change point,
all four extractors benefit; the tools array precedes system in the cached prefix
automatically, and prompts below a model's minimum cacheable length are silently not
cached, so the block form is sent unconditionally. The modeler's byte-identical system
prompt across MAX_MODELING_ATTEMPTS retries is the main win. (2) Errors-only retry
feedback: on a re-model, dv2_modeler sends only severity=="error" issues, each reduced to
exactly code/construct/message (attribute access on the WP4 ValidationIssue) — warnings
are advisory for humans, not steering input. (3) Input-size guard: extracted document
text longer than MAX_DOCUMENT_CHARS (400_000, ~4 chars/token heuristic; lives in
agents/requirements_parser.py, deliberately not in rules/ — it is not a DV rule) is cut
to the head and flagged FlagKind.INPUT_TRUNCATED (advisory, asset = document path,
message names both sizes) — never silently truncated; the pipeline continues on the head
and the human decides. Keyless tests pin the cache-controlled request shape via the
tests/test_llm.py stub client, the errors-only three-field retry payload (and its absence
when only warnings exist), and the truncation boundary + flag (at-limit documents are
untouched and unflagged). 174 tests green, ruff clean, mypy strict clean.

The eval harness landed (as of 2026-07-08, WP6:
docs/architecture/backlog-2026-07/wp6-eval-harness-spec.md) — the declared LangSmith-evals
milestone, in three strictly separated layers under eval/. Layer 1: golden datasets
(eval/datasets/<case>/dataset.yml — bank from the Postgres-verified end-to-end PoC model with a
construct_f1>=0.5 gate, health_insurance from the demo walkthrough with driving_key
hub_policy on link_insured_person_policy, messy_insurance loose/ungated as a
review-queue-regression canary) with a typed loader (eval/datasets.py: EvalCase/GoldenModel,
attributable errors in the source_schema.load_source_schemas style). Layer 2: four
deterministic scorers (eval/scorers.py: construct_f1, driving_key_accuracy,
validation_gate, pipeline_health), all matching *structurally* through
rules.normalize_identifier, keyless and pinned-score-tested. Layer 3: the live runner
(`python -m eval.run --dataset <case> [--all] [--repeat N]`) runs the real graph per
repeat (MemorySaver, HITL checkpoint auto-resumed like `vault-agent resume --accept`),
writes one JSON result per run (scores, details, model ids, git SHA) under eval/results/
(git-ignored), prints mean/min/max per scorer across repeats, and exits 1 when a mean
falls below the case's optional min_scores — a manual pre-release gate, no CI wiring.
The optional LangSmith layer (eval/langsmith_upload.py) is import-guarded: with
LANGSMITH_API_KEY plus the `eval` extra it creates one dataset per case and logs runs
with scores as feedback; without either it is a no-op, and the default test suite needs
neither a key nor the langsmith package. mypy now also checks eval/ ([tool.mypy] files).
210 tests green, ruff clean.

WP7 staging refinements landed (as of 2026-07-08,
docs/architecture/backlog-2026-07/wp7-staging-refinements-spec.md), closing the staging
generator's three recorded deferrals, all deterministic. Guard first: an ungrounded run
over the bank end-to-end PoC model is pinned byte-identical to the pre-WP7 output
(tests/fixtures/staging_ungrounded_baseline/ + test_staging_regression.py, written before
the changes) — WP7 only alters grounded / source_table / contract-matched output. (§7.1
ma_sat grain) Satellite gains source_table (the raw relation its rows come from when it
differs from the parent's); a satellite declaring it gets its own staging model
(stg_<sat base>: parent HK hashed from the parent's BK — the BK column must exist in the
finer-grain relation — plus own hashdiff, cdk, attrs), bound VERBATIM (declared, never
flagged), and _render_sat/_render_ma_sat read it as source_model; effectivity satellites
keep the parent link's staging. New validator warning W_MASAT_SHARED_GRAIN (28 E_/W_
codes now) when a multi_active satellite has no source_table; matching [GUIDE] line in
DV_MODELING_RULES; the modeler tool schema picks the field up from the pydantic model
(pinned by test). (§7.2 source() binding) SourceTable gains schema_name (input alias
`schema`) and database, accepted by the loader; on grounded runs, staging specs bound to
a declared table that carries a physical location render AutomateDV's source() mapping
form (source_model: {raw: '<table>'}, verified against the 0.11.4 stage docs) and
sources.yml becomes a real source definition — one block per distinct (database, schema),
deterministically named raw, raw_2, … in staging-spec insertion order. Declared tables
WITHOUT schema/database deliberately keep bare-name references (a dbt source without a
schema property defaults its schema to the source name, which would break the verified
bare-name/seed pattern); they are documented in a sources.yml trailing comment, and
inferred bindings keep their SOURCE_BINDING flag. (§7.3 seed types) build_staging takes
state.artifacts.contracts (drafted upstream — graph order data_contract before
code_generator makes this possible; do not reorder); a staging source whose contract
matches by normalised name gets seeds.<project>.<source>.+column_types per the fixed
mapping (string→varchar, integer→bigint, number→numeric, boolean→boolean,
string+format=date→date, date-time→timestamp via the field's semantics, unions take the
single non-null member, unknown/ambiguous OMITTED — left to dbt inference, never
guessed); LOAD_DATETIME/RECORD_SOURCE always timestamp/varchar. The Postgres hardness
re-verification REQUIRED by the original handover was performed 2026-07-08 in a clean
environment, all three scenarios green: (A) ungrounded fresh output incl. a ma_sat with
source_table — `dbt deps` → `dbt seed` → `dbt build --full-refresh` PASS=15, incremental
re-run idempotent, sat_customer_addresses populated on its own stg_customer_addresses
with the parent CUSTOMER_HK joining hub_customer for every row (the §7.1 correctness
property); (B) grounded run with declared schema (raw_core) — staging bound via the
source() mapping form, `dbt build` green with NO seeds (PASS=9, raw tables materialised
directly in raw_core), sources.yml carried the real schema; (B2) two-phase snapshot load
against the raw_core tables closed ACC-503's superseded ownership to 2026-04-01 with the
successor open — identical behaviour to the seed-based path. 239 tests green, ruff clean,
mypy strict clean.

WP5 hygiene batch landed (as of 2026-07-08,
docs/architecture/backlog-2026-07/wp5-hygiene-spec.md), six cleanups. (§5.1) The
review-queue presentation knowledge (KIND_HEADINGS/KIND_ORDER) is public in
agents/orchestrator.py and imported by cli._print_checkpoint — one owner, parity-tested;
the former cli duplicates are gone. (§5.2) BaseAgent.prompt_path is
ClassVar[str | None] = None and load_prompt() raises RuntimeError naming a prompt-less
agent; the deterministic agents lost their dead prompt_path lines, all nine
`# type: ignore[assignment]` are gone, the four never-loaded prompt files
(validator/orchestrator/code_generator/adr_author.md) and the empty tools/ package are
deleted (grep-verified unreferenced first). (§5.3) jinja2 (imported nowhere) is out of
pyproject; config drops the dead log_level; the langsmith_* settings stay (WP6's eval
harness consumes them). (§5.4) Std-lib logging: logger per module, INFO at agent-run
boundaries with construct counts, DEBUG for payload sizes; the library never configures
handlers/levels — the CLI's new global `--debug` flag sets basicConfig(DEBUG) and
re-raises pipeline failures with the full traceback; default CLI output is unchanged.
(§5.5) A finalised run prunes its checkpoint thread via AsyncSqliteSaver.adelete_thread
(verified against the installed langgraph-checkpoint-sqlite) inside
_run_pipeline/_resume_pipeline; paused runs keep their thread for resume —
checkpoints.sqlite no longer grows unboundedly (tested against the real sqlite saver).
(§5.6) Doc drift: the "interrupt() is the node's first statement" claim (here and in the
HumanCheckpointAgent docstring) is reworded to the actual invariant — everything before
interrupt() stays pure/idempotent because the node re-executes on resume. 235 tests
green, ruff clean, mypy strict clean.

WP8 role-qualified link hub references landed (as of 2026-07-08, ADR-0009 Accepted,
docs/architecture/backlog-2026-07/wp8-multi-role-links-spec.md), closing the
self-referencing-link gap (poc-end-to-end-dbt-spec §9, reality-test #5). A link hub
reference is now Link.connected_hubs: list[str | LinkHubRef] — a plain string is an
unqualified participation, a LinkHubRef(hub, role) (or {"hub", "role"} dict) role-qualifies
one so the SAME hub can take part twice (e.g. a transfer's paying account + counterparty
account). A before-validator normalises every entry to LinkHubRef; downstream code reads
one shape via Link.hub_refs (a property that re-coerces defensively, since field assignment
skips validation), and driving keys — which may name "hub" or "hub:role" — resolve through
Link.resolve_driving_refs(). The declared union keeps plain-string YAML/tool-schema/tests
working and model_dump round-trips through the checkpointer. Naming is a single source of
truth in rules/dv2_rules.py: role_fk_column("ACCOUNT_HK","counterparty")==
"COUNTERPARTY_ACCOUNT_HK" and role_bk_column("ACCOUNT_NUMBER","counterparty")==
"COUNTERPARTY_ACCOUNT_NUMBER"; both are identity for role=None, so unqualified refs render
byte-identically (acceptance criterion #1, pinned by test_staging_regression + the demo
guardrail + a dedicated backward-compat test). Ripple (each tested): the code generator
role-qualifies src_fk (new _link_src_fk helper) and the eff_sat driving/secondary FK split
on resolved refs; the staging generator hashes role-qualified FK columns from role-qualified
BK columns (a self-referencing raw table carries the two participations as two columns); the
validator gains E_LINK_DUP_ROLE (two participations with identical (hub, role)) and the
grounded W_ROLE_BK_NOT_IN_SOURCE, and makes E_LINK_UNKNOWN_HUB / E_DRIVING_KEY_NOT_IN_LINK /
W_LINK_REDUNDANT_GRAIN role-aware (grain = multiset of (hub, role); validator code count 30);
adr_author renders refs as "hub_account (counterparty)"; the modeler prompt + DV_MODELING_RULES
gain a [GUIDE] line; eval/scorers matches links on the hub set. The bank demo gains a
self-referencing transactional link_transfer (hub_account + hub_account as counterparty,
payload amount/currency, seed raw_transfer.csv, hand-authored stg_transfer, _raw_vault.yml
tests, README + Files) via build_bank_dv_model_with_transfer() — the plain
build_bank_dv_model() stays the byte-identity baseline; the generated link_transfer.sql
emits src_fk=["ACCOUNT_HK","COUNTERPARTY_ACCOUNT_HK"] and stg_transfer hashes both.
Verified end-to-end on PostgreSQL 16 + AutomateDV 0.11.4 (2026-07-08): `dbt build
--full-refresh` green (PASS=36 WARN=0 ERROR=0), link_transfer materialising DISTINCT
account_hk / counterparty_account_hk columns (not_null + unique pass; account that both pays
and receives hashes to the same value in each role). This Postgres run exposed and fixed a
latent generator bug — the transactional-link template emitted the non-existent
automate_dv.nh_link; AutomateDV's macro is t_link (with a required src_extra_columns arg,
passed as none). Never caught before because no transactional link had ever been built
end-to-end; the standard-link/hub/sat/eff_sat path was unaffected. Also fixed a latent bug in
build_vault_models.py main() (referenced the removed state.errors → now state.flags). pytest /
ruff / mypy (canonical `uv run mypy`, 28 files) green.

The business↔source mapping design spike ran and resolved Phase 2 (as of 2026-07-12/13,
spike-mapping-charter.md → docs/architecture/backlog-2026-07/spike-mapping-results.md). It
measured, on the deliberately cryptic messy_insurance case, an LLM-first mapper (one
ForcedToolCaller pass over the enriched schema + profiling + comments, then deterministic
post-validation) against a deterministic-first hybrid: LLM-first won mapping_accuracy 0.984
vs 0.650, gap recall 1.000, confidence-calibration margin 0.958 vs 0.000, at LOWER input-token
cost, and resisted every trap (kept "partner number"→PARTN_NR over the flawless-profiling
PARTN_GUID; zero false-friend hits; caught all 4 coverage gaps every run). NO src/vault_agent/
code changed — this was a design spike. Surviving assets (D1/D2, keyless, tested): eval/mapping.py
(typed ProposedMapping/Proposal result + GoldenMapping loader, WP6 style), three scorers in
eval/scorers.py (mapping_accuracy/gap_detection/confidence_calibration, structural matching via
normalize_identifier), tests/test_mapping_scorers.py (15 pinned), and
eval/datasets/messy_insurance/{golden_mapping,profiling,source_schema_enriched}.yml (golden set
embedding the five trap classes + profiling + a type/comment-enriched schema). The throwaway
prototypes (spike/) were deleted. Outcome: ADR-0008 moved Proposed → Accepted (2026-07-13), with
ONE recorded caveat — the "input quality caps output quality" claim is confirmed for the
deterministic path but UNPROVEN for the LLM path (the columns-only probe did not degrade because
the schema's cryptic names are recognisable DACH abbreviations the model knows from priors; a
mandatory opacity-masked probe, physical names → COL_0001…, is a WP9 acceptance criterion). Key
methodological finding on naming: the rename layer splits by column role — a hub business key MUST
be harmonised to one canonical name+format (the hash integration property forces it; "keep source
names" is impossible for a multi-source key), while satellite descriptive attributes stay
source-faithful (one sat per source). The multi-source hub is not representable in today's Hub
model / _render_hub (single source_model + src_nk), so the work is specced as WP9 (single-source
mapping binding, LLM-first, ratification file + --map shortcut, category-based confidence gate) +
WP10 (multi-source hub: Hub.sources, per-source staging with canonical-key aliasing, union hub,
sat-per-source), each with a kick-off. Also fixed a pre-existing test-hermeticity bug: eval.run's
no-key test (test_main_without_api_key_exits_2) was defeated by main()'s load_dotenv() repopulating
the key from a real .env — which also made the "keyless" suite fire 3 real bank LLM calls; the test
now neutralises load_dotenv, so the suite is keyless and fast again (285 passed). ruff / mypy
(29 files) green.

WP9 business↔source mapping landed (as of 2026-07-13, ADR-0008 Accepted,
docs/architecture/backlog-2026-07/wp9-mapping-spec.md), the single-source half of Phase 2. A new
LLM agent (agents/source_mapper.py, SourceMapperAgent) proposes, per validated-model concept (hub
business keys + satellite attributes), which physical source column feeds it — or that it is a
coverage gap — then deterministic post-validation demotes any pick naming a non-existent column to
unresolved (never invents a column, the spike's safety property). It productionises the spike's
LLM-first mechanism: one ForcedToolCaller pass (Sonnet-tier, prompt in prompts/source_mapper.md,
injectable MappingProposer for keyless tests) over the enriched schema + profiling + comments.
Inputs (both inert-compatible, ADR-0004 byte-for-byte guard): state.SourceColumn makes
SourceTable.columns a list[str | SourceColumn] union (name/type/comment; bare strings coerce, read
via .column_names) so a schema can carry the type+comment ADR-0008 precondition (c) wants; a new
profiling.py load_profiling producer feeds state.profiling (CLI `run --profiling <file>`);
state.Proposal/ProposedMapping are promoted into state.py (re-exported by eval/mapping.py — one
definition) with a §7 deterministic confidence category
(exact_name>comment_grounded>profiled_key>llm_semantic) and a ratification_status. Graph: the
mapper runs on the validated path (validator --pass--> source_mapper --> human_checkpoint -->
adr_author). NB the spec's §4 diagram placed it before code generation, but the validator validates
the code generator's artifacts (_check_artifact_columns), so code generation cannot move after the
validator — the mapper runs post-validation and re-binds staging itself (build_staging/bind_sources
gained source_overrides: a ratified hub-key mapping binds its staging to the real source table,
clearing the SOURCE_BINDING flag; empty overrides leave the WP7 inference byte-identical). HITL:
gaps/unresolved join the ADR-0006 review queue (FlagKind.MAPPING_GAP/MAPPING_UNRESOLVED,
aggregatable; requires_signoff unchanged — a gap is honest output, not a blocker); write_outputs
emits mappings.review.yml; `resume --mappings <edited file>` / `--map "concept=TABLE.COLUMN"`
ratify via apply_human_decision (promotes unresolved/gap concepts, prunes their flags, re-binds
staging). Multi-candidate business keys (the same key in two sources) are NOT force-picked — they
land in unresolved with both candidates in evidence and a WP10 pointer (Hub.sources is WP10). The
mapper is inert when ungrounded (no source_schemas -> no LLM call, byte-identical). Eval: the D2
mapping scorers are wired into eval/run.py against a case's golden_mapping.yml; a bank golden
mapping (easy/high-floor case) added. Verified live end-to-end (2026-07-13): HITL ratification
(`resume --map`) re-bound stg_customer->customer / stg_account->account with the mapping flags
pruned and the run finalised. (NB the WP9 build had an over-deferral bug — it treated an FK
occurrence of a key in a relationship/transaction table as a second source and parked hub keys in
`unresolved`; fixed in WP9.1 below. This paragraph originally miscelebrated that as a feature.)
Two REQUIRED acceptance items remain as open human-verification steps (heavier new measurements):
§10.7 the opacity-masked degradation probe (physical names -> COL_0001…, closes the ADR-0008
precondition-(c) caveat) and §10.8 a Postgres build of a grounded+profiled+ratified single-source
run. Also surfaced (pre-existing, NOT WP9): the data_contract agent truncates at max_tokens=4096 on
the 6-table messy schema, so the full messy `run` cannot complete end-to-end today — flagged, out
of WP9 scope.

WP9.1 mapping remediation landed (as of 2026-07-13,
docs/architecture/backlog-2026-07/kickoff/WP9.1-mapping-remediation.md), fixing three review
findings against WP9. (F1) Over-broad multi-source deferral: the mapper treated an FK occurrence of
a business key inside the SAME source system (a key column in a relationship/contract/transaction
table, e.g. VICTOR_VERTRAG.PARTN_NR "FK to VICTOR_PARTNER.PARTN_NR", or bank account_customer's
national_customer_id) as a second source and parked the hub key in `unresolved`, so §6 auto-binding
never fired and live messy accuracy sat at 0.870 (below the spike band). Fix: prompts/source_mapper.md
now defers ONLY across DIFFERENT source systems (VICTOR entity table vs. CRM entity table); an
FK reference to another candidate's table is not a second source — map to the entity-anchor table.
Plus a deterministic belt-and-braces FK-demotion in _post_validate (keyless-testable): when the
proposer defers a business_key with >= 2 TABLE.COLUMN candidates in its evidence and all but one
candidate's SourceColumn.comment marks it an FK to the remaining anchor's table, it auto-resolves to
the anchor (evidence += fk-demotion); no comments / genuinely cross-system stays unresolved (honest,
WP10). (F2) rebind_staging now applies the FULL build_staging result — staging_models,
automatedv_yaml["staging"] metadata, and scaffolding — not just the models, so a re-bind can't leave
stale metadata/sources.yml behind. (F3) this milestone's WP9 paragraph corrected (above). Re-measured
live (2026-07-13): messy_insurance 5 repeats mapping_accuracy 0.980/0.980/0.960/0.980/0.960 (mean
0.972, all >= the 0.95 gate; precision 1.00 every run so the statistics trap stays correct —
partner number -> PARTN_NR, never PARTN_GUID; gap_detection 1.000; the synonym "customer reference"
stays unresolved, scorer-acceptable per memo thin-evidence #4). 310 tests green (keyless; +4 WP9.1
tests: FK-demotion resolve / no-comment-stays / cross-system-stays / rebind-consistency), ruff clean,
mypy strict clean (31 files). §10.7/§10.8 remain open as under WP9.

WP9.2 mapping-scorer universe fix landed (as of 2026-07-13,
docs/architecture/backlog-2026-07/kickoff/WP9.2-mapping-scorer-universe.md), eval-only. The live
bank eval scored the mapper's proposals for GENERATED-model concepts the golden mapping doesn't
cover (transactions/addresses) as "wrong" (precision 0.67, F1 0.80) and their confidence collapsed
the calibration margin — an eval-design artefact (the spike prototypes were fed the golden model's
concepts; the pipeline maps the generated model's). Fix (eval/scorers.py only, no src change):
mapping_accuracy and confidence_calibration score ONLY proposals whose concept is in the golden
"universe" (mappings + gaps + ambiguous); out-of-universe proposals are reported, not penalised;
the no-wrong-proposals calibration margin is defined as 1.0 (perfect separation). gap_detection's
force-fit check stays global by design. bank now scores mapping_accuracy F1=1.00, so its
min_scores.mapping_accuracy gate (deferred by WP9 §8) is set to 0.95. eval/README scorer semantics
updated; +3 pinned tests (out-of-universe ignored, no-wrong margin=1.0).

WP9 §10.7 opacity probe closed (as of 2026-07-14), shutting the ADR-0008 precondition-(c)
measurement gap the spike recorded as unproven (spike memo thin-evidence #1). eval/opacity_probe.py
is a deterministic, keyless-tested masking transform (physical column names -> COL_NNNN, optionally
table names -> TBL_NN, comments + example values stripped, types + distributions kept, the golden
set re-keyed) plus a live probe that re-runs the PRODUCTION mapper. Measured (3 repeats/config):
mapping_accuracy degrades monotonically as documentation is removed — 0.972 (real names) -> 0.902
(columns masked) -> ~0.88 (columns + tables masked) — with unresolved rising, gap recall becoming
uncertain, and the confidence categories collapsing entirely from name-based
(exact_name/comment_grounded) to structural (profiled_key/llm_semantic), while confident-wrong
proposals stayed at ZERO across all runs. So "input quality caps output quality" is confirmed for
the LLM path AND the essential guarantee holds: the mapper degrades honestly (resolves structurally
at lower confidence, or defers to unresolved) and never confidently hallucinates. Nuance: accuracy
stays ~0.88 even at maximal opacity because types + profiling + the concept list still carry
structural signal — column names are not the sole driver. WP9 §10.8 (Postgres re-verification of a
grounded+profiled+ratified single-source run) remains the one open WP9 verification item. 325 tests
green (keyless; +3 mask-transform tests), ruff clean, mypy strict clean (32 files).

WP10 multi-source hub landed (as of 2026-07-14,
docs/architecture/backlog-2026-07/wp10-multi-source-hub-spec.md), the canonical DV2.0 integration
case: one business key living in several source systems -> one hub. state.Hub gains
sources: list[HubSource] (per feed the physical key column); empty = single-source, today's
behaviour (byte-identity guard, pinned first — the existing hub-SQL/staging-regression tests plus a
new empty-sources assertion). rules.canonical_hub_key_column() decides the staging key name in ONE
place: a business term (normalised business_key) ONLY when the feeds disagree on the physical column
name, else the source's own name (no gratuitous rename — WP9 §6 policy). Generation: the staging
generator emits one stg_<entity>_<source> per HubSource, each aliasing its physical key column to the
canonical name via derived_columns and hashing X_HK from it — so the SAME key value hashes
identically across feeds (the integration property); _render_hub emits source_model as a LIST (the
AutomateDV 0.11.4 postgres__hub macro unions a source_model list and DISTINCT-ONs the PK — verified
against the installed macro, not memory, per the WP8 t_link lesson) with src_nk = the canonical
name; a satellite on a multi-source hub splits into one sat_<entity>_<source> per source, each
reading its own staging (record_source distinguishes the feeds, value harmonisation stays in the
Business Vault — spike Q6). Validator: E_HUB_DUP_FEED (two HubSources naming the same (table,
column)) and per-source W_HUBSOURCE_BK_NOT_IN_SOURCE grounding. WP9 hand-off: the ratification file
gains a sources: form (apply_human_decision resolves a ratified multi-candidate key into Hub.sources,
prunes its unresolved flag; a fresh run then renders the hub multi-source — mid-run resume
regeneration of a newly-multi-source hub is a documented follow-up). Same-as links (asserted-
equivalent but DIFFERING keys) stay explicitly deferred — flagged, never merged. Proven end-to-end
on PostgreSQL 16 + AutomateDV 0.11.4 (2026-07-14): a hub fed by crm_customer(cust_id) +
victor_partner(partn_id), with the same customer 'C001' in both, built green (dbt build PASS=7
WARN=0 ERROR=0, "hub_customer from 2 source(s)") to ONE hub row for C001 (3 rows total for
C001/C002/C003) with an IDENTICAL CUSTOMER_HK across the crm stage, the victor stage, and the hub
(crm_eq_victor = true), and the two per-source satellites split by record_source. 322 tests green
(keyless; +10 WP10 tests: canonical policy, hash-input identity, source_model list, sat-per-source,
byte-identity, duplicate-feed error, per-source grounding, ratification round-trip), ruff clean,
mypy strict clean (31 files).

WP9 §10.8 closed (as of 2026-07-14) — the last open WP9 verification item: a Postgres hardness
build of a grounded + profiled + ratified SINGLE-source run. A live bank run
(examples/inputs/bank_account_requirements.md + the new bank_source_schema_enriched.yml
[types+comments, ADR-0008 precondition (c)] + bank_profiling.yml) exercised the real
SourceMapperAgent: it resolved all 9 concepts by exact_name (0 gaps, 0 unresolved; correct
FK-vs-anchor reasoning — national_customer_id→customer, not the account_customer FK — the WP9.1
demotion), ratified via `resume --accept`, and the generated dbt project built green on
PostgreSQL 16 + AutomateDV 0.11.4: `dbt build --full-refresh` PASS=17 WARN=0 ERROR=0, incremental
re-run idempotent (row counts unchanged), all 7 raw-vault constructs populated (2 hubs,
link_account_customer, self-referencing link_transaction with distinct role FKs, 2 standard sats,
1 eff_sat), the hub carrying the ratified source-faithful key national_customer_id (§6, no
gratuitous rename). The build surfaced and fixed a latent generator bug (same class as WP8's
t_link): staging_generator._render_sources_yml listed a physical source table once per staging
spec, so two specs binding to the same relation (a hub's staging plus a satellite whose
source_table names the hub's own relation, which the modeller had done) emitted DUPLICATE
sources.yml table entries and dbt raised a duplicate-source compilation error; a new
_merge_source_tables dedups by relation (expected columns unioned in first-appearance order,
byte-identical output when every spec already has a distinct source table, so all staging
fixtures are unaffected). 326 tests green (+1: test_sources_yml_lists_each_source_table_once),
ruff clean, mypy strict clean (32 files). Every WP9 acceptance item is now MET. The §10.8
build was then promoted to a permanent, re-runnable demo (demo/mapping_postgres/, 2026-07-15):
a deterministic no-API-key build script (build_vault_models.py — the fixed bank model, the
declared enriched schema, and the ratified accepted mapping, run through the real
CodeGeneratorAgent + rebind_staging) that emits GROUNDED+RATIFIED staging bound to the real
business-named source tables (customer/account/account_customer — zero inferred-binding flags,
the contrast with the ungrounded demo/bank_postgres) and builds green on PostgreSQL 16 +
AutomateDV 0.11.4 (dbt build --full-refresh PASS=12, incremental idempotent). Guardrail:
tests/test_demo_mapping_postgres.py (bindings, zero flags, idempotency, sources.yml dedup).

The data_contract truncation bug is fixed (as of 2026-07-15) — the pre-existing blocker the
WP9 paragraph above flagged (max_tokens=4096 on the wide messy schema). The enricher drafted
ALL assets in one ForcedToolCaller call, so the combined enrichment exceeded the cap and WP3's
max_tokens guard raised LLMCallError, killing the run. DataContractAgent.run now enriches in
BOUNDED units (agents/data_contract.py), scaling in BOTH dimensions: one asset per call (so a
wide *schema* — many tables — never overflows), AND a table wider than _FIELDS_PER_CALL (40)
is further split by field into ceil(cols/40) calls (so a wide *table* — many columns, routine
in legacy insurance/banking sources — never overflows either; _merge_enrichment folds the
chunks back per asset). The system prompt (carrying the full declared schema) is byte-identical
across calls, so WP3 prompt caching makes the extra calls cheap on input tokens; the per-call
output budget is 8192 (output tokens billed per generation, so headroom is free). Verified live:
(a) 5-table/38-column messy_insurance — 5/5 contracts, all 38 fields typed, 0 undetermined-type
flags; (b) a 256-column table — 7 bounded calls (ceil(256/40)), all 256 fields contracted, no
truncation (both previously LLMCallError). Keyless tests:
test_enrichment_is_batched_one_asset_per_call (one call per asset) and
test_wide_table_is_chunked_and_fully_enriched (256 cols → chunked, full field coverage).
331 tests green, ruff clean, mypy strict clean (32 files).

With that blocker gone, the FULL messy_insurance pipeline now completes end-to-end (verified
live 2026-07-15) — the case the WP9 paragraph flagged as unable to finish. `vault-agent run`
over examples/inputs/messy_insurance_requirements.md +
eval/datasets/messy_insurance/source_schema_enriched.yml + …/profiling.yml ran every agent
(requirements 34 → business keys 10 → 5 contracts → model 4 hubs / 5 links / 13 sats → validation
PASSED → source_mapper 32 exact_name proposals, 0 unresolved, 2 honest gaps) to the HITL
checkpoint, then `resume --accept` (5 contract owners assigned) finalized it: 22 raw-vault + 17
staging models, 5 contracts, ADR-0001, mappings.review.yml. Notably the multi-source hub (WP10)
fired on the real case — hub_partner integrates VICTOR_PARTNER + CRM_ACCOUNT with per-source
satellites — and the mapper correctly flagged effective_from/effective_to as Business-Vault gaps
rather than forcing a source. Two honest advisory flags surfaced for human review (not blockers):
an effectivity satellite the modeller left without a driving_key, and 4 inferred staging bindings.
This was a verification run (no code change).

Modeler CDK-dedup fix (as of 2026-07-16): re-running the health_insurance demo to refresh the
walkthrough's figures exposed that it FAILED validation 4/4 — every run tripped E_SAT_DUP_ATTR on
the multi-active sat_insured_person_address because the modeler listed the child_dependent_key
(address_type) ALSO among the satellite's attributes, so the generated sat would emit that column
twice (src_cdk + src_payload). The re-model loop couldn't recover within MAX_MODELING_ATTEMPTS. Fix
(both belt-and-braces, since LLM steering alone failed 4/4 even with the error fed back): a [GUIDE]
line in DV_MODELING_RULES telling the modeler a multi-active CDK is a key column, not payload; and a
deterministic rules.attributes_without_cdk(attributes, child_dependent_key) that dv2_modeler applies
in _validate_model — it drops payload attributes normalising to a CDK label (order-preserving,
meaning-preserving: the CDK column still ships via src_cdk), while genuine attr-vs-attr duplicates
stay for E_SAT_DUP_ATTR to flag. After the fix the demo PASSES 3/3 (0 issues); a representative run
is 4 hubs / 3 links / 8 satellites → 15 raw-vault + 8 staging models, matching the walkthrough. 333
tests green (+2: attributes_without_cdk unit + the modeler-dedup integration), ruff clean, mypy
strict clean (32 files). docs/demos/health-insurance-walkthrough.md figures refreshed.

WP11 static HTML run report landed (as of 2026-07-18, UI-track stage 1,
docs/architecture/backlog-2026-07/wp11-html-run-report-spec.md). A new deterministic,
presentation-only module (src/vault_agent/report.py: build_report(state),
build_model_mermaid(model) — no LLM, no agent, no business logic) emits one self-contained
report.html per run, written unconditionally by cli.write_outputs (counts gains "report": 1;
both the interrupt path and the finalize path call it, so a paused run's report shows the
pending state and a resumed run overwrites it). The DV model is rendered as a Mermaid
flowchart whose *source text* is generated in pure Python (browser does layout): hubs are
rectangles, links hexagons (transactional annotated), satellites rounded rectangles with one
class per sat_type; a multi-source hub (WP10 Hub.sources) gets one cylinder per feed, link
participations read through Link.hub_refs (never raw connected_hubs) with the role as edge
label and a driving-key participation (resolve_driving_refs()) as a thick ==> edge, a
WP7-§7.1 sat source_table noted in the label; node IDs via rules.normalize_identifier (one
normalisation source), emission order deterministic (hubs, links, sats in model order).
Sections: header (counts + grounding from state.plan + validation/sign-off badges), graph,
construct inventory (3 tables), validation (WP4 ValidationIssue attribute access), review
queue (the THIRD renderer over the WP5 §5.1 API — imports KIND_HEADINGS/KIND_ORDER/
aggregate_review_flags, never duplicates that knowledge), mappings (conditional), contracts
(placeholder owner → "⚠ unassigned" matched on ContractOwner.PLACEHOLDER_NAME), and a
collapsed generated-files list. Determinism: no timestamps/env — byte-identical output for
identical state (pinned fixture tests/fixtures/report/report_fixture.html). Security: every
LLM-derived string passes html.escape (and Mermaid-label escaping) — treat all state strings
as hostile; the document carries exactly ONE raw <script>, the pinned Mermaid v11 UMD CDN
include (dist/mermaid.min.js — verified present on jsdelivr, not from memory), whose own
onload initialises+runs Mermaid (securityLevel:'strict') and whose onerror un-collapses the
always-present graph-source <details> so a CDN-blocked report stays fully readable. No new
runtime dependency (stdlib templating only — jinja2 stays removed). Verified deterministically
on the bank-with-transfer demo model (report.html generated keyless, well-formed, self-ref
link_transfer renders two edges to hub_account incl. the counterparty role, one script tag).
The manual browser check (spec DoD) was performed 2026-07-18 and passed: the graph renders
online and, with the CDN blocked, the report stays readable with the graph-source details
auto-expanded. Acceptance #2 (messy_insurance multi-source render) was exercised via the
equivalent checked-in model shape in tests, not a live LLM run. 339 tests green (+6 in
tests/test_report.py: fixture/idempotency, hostile-name escaping, Mermaid structure, review
parity, empty-state; the 2 cli count assertions updated for the new "report" key), ruff
clean, mypy strict clean.

WP12 interactive checkpoint prompt landed (as of 2026-07-18, UI-track stage 1.5,
docs/architecture/backlog-2026-07/wp12-interactive-resume-spec.md). The HITL checkpoint is now
answerable directly in the terminal instead of re-typing a `vault-agent resume …` command.
cli.py only (+ tests): `run` and flag-less `resume` gain --interactive/--no-interactive
(default auto = both stdin and stdout are TTYs, via _is_interactive; non-TTY — CI, pipes,
tests — keeps today's print-and-exit path byte-identical, pinned). On a pause the loop
(_interactive_checkpoint) walks the actionable items — a contract with a placeholder owner
(matched on ContractOwner.PLACEHOLDER_NAME, never message text) is prompted, each single-source
unresolved mapping is prompted for TABLE.COLUMN, and a multi-source key (detected structurally:
its normalised name is a column in >= 2 declared source tables — never by parsing the flag
message) is listed with the resume --mappings pointer, never prompted (capability-parity rule:
the prompt offers only what the resume flags offer). A malformed answer re-prompts via the
existing _parse_owner; an accept confirm mirrors --accept and gates the commit. Confirmed input
is assembled by the existing _build_decision and resumed in-process via _resume_pipeline (the
flag-less resume loads the paused state from its checkpoint through a new _paused_state helper /
compiled.aget_state); decline / skip-all / Ctrl-C leaves pending.json + the checkpointer thread
intact and prints today's resume instructions (abort never loses the checkpoint). No decision
semantics live in the loop — it only collects strings; apply_human_decision, the graph, and
state are untouched. Prompting goes through an injectable module seam (_prompter, rich
Prompt/Confirm) so the whole flow is keyless- and TTY-free-testable. No new dependency (rich
already present). Acceptance #1 verified keyless end-to-end against the real stub graph
(a paused run finalised entirely through the prompt, checkpoint cleared + thread pruned).
The spec-DoD real-terminal smoke test was then performed 2026-07-18: a genuine paused run
(real AsyncSqliteSaver, placeholder-owner contract) driven through the actual
`vault-agent resume` CLI attached to a pseudo-terminal (pty → isatty() true → auto
interactive) with the owner + accept *typed* — finalised, checkpoint cleared, thread
pruned, and the outputs (report.html, review-queue.md, contract) are BYTE-IDENTICAL to the
same paused run resumed via `resume --owner … --accept` (parity / capability-equivalence
proven, acceptance #1's byte-identical clause). 348 tests green (+9 in
tests/test_cli.py: tri-state/flag matrix, non-TTY regression, invalid-input re-prompt,
multi-source deferral, owner+accept decision parity, abort-keeps-checkpoint, _paused_state
load, end-to-end interactive finalize), ruff clean, mypy strict clean.

## References
- In-repo methodology notes: docs/methodology/ (DV2.0 rules cheatsheet, IREB mapping, DSAF
  mapping, data-contracts approach)
