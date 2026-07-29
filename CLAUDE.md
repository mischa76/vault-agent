# Vault-Agent – Project Context for Claude

## Mission
Build a multi-agent system that automates Data Vault 2.0 modeling and code generation
from business requirements documents. Target market: Swiss/DACH enterprises with large
DWH landscapes (banks, insurers, pharma, mid-market).

## Author
Mischa Eismann (eismann.consulting) — CDVP² (Data Vault 2.0 Practitioner, 2015), 20+ years in ICT.

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
- Data Vault 2.0 (Dan Linstedt / DataVaultAlliance) – methodology and rules
- DSAF (Roelant Vos) – Data Solutions Architecture Framework: a pragmatic architecture lens
  (influence, not an implemented/selectable mode). Adopted ideas and the ADR-gated Vos
  alternatives are critically mapped in docs/methodology/dsaf-mapping.md
- IREB CPRE Foundation – Requirements Engineering conventions
- Chad Sanderson, Mark Freeman & B.E. Schmidt – Data Contracts: Developing Production-Grade Pipelines at Scale (O'Reilly, 2025)
- Andrej Karpathy – LOOPS.md: Field Notes on Agents That Run for Days (working notes,
  v060726, 2026) – agent-loop/harness design principles (role separation, state on disk,
  contract-first, trace reading). Adopted post hoc as a lens, not a blueprint: the
  convergent matches and the ONE deliberate deviation (rule VIII "delete the harness" does
  not apply to the validator gates — they are product, not model-compensation) are
  critically mapped in docs/methodology/loops-mapping.md; WP15/WP16 operationalise
  rules VII/VIII

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

Hardening batch P1+P2 landed (as of 2026-07-06, see
docs/architecture/reviews/project-review-2026-07-06.md). (P1) The
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

The staging generator landed (as of 2026-07-06, P3 from
docs/architecture/reviews/project-review-2026-07-06.md): the
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
(same state AND date in → byte-identical ADR out — the date qualifier is a WP26 correction:
`today` is injectable but defaults to the clock, so this paragraph originally overclaimed);
repo-level ADR numbering happens only when a human
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

WP13 scale-hardness *tooling* landed (as of 2026-07-18, Charter A / roadmap;
docs/architecture/backlog-2026-07/wp13-scale-hardness-spec.md), the keyless half — the live
measurement protocol (spec §4) is the maintainer's, executed afterwards. Three pieces.
(§2 generator) eval/scale/generate.py (`python -m eval.scale.generate --tables N --seed S
--out DIR`) synthesises a mutually-consistent landscape of exactly N source tables across
three systems (a cryptic DACH legacy system, an anglophone CRM, a peripheral system):
source_schema.yml (types+comments, ADR-0008 precondition-(c) shape), profiling.yml (incl.
the statistics trap — a technical GUID profiling 1.0/0.0 next to the true key's realistic
null wart), requirements.md (a business-entity/relationship narrative that scales with the
entity count — deliberately NOT an exhaustive per-table inventory, see the breakpoint note
below), and golden_mapping.yml (a sampled ~30-concept universe, WP9.2 semantics, NOT one per
table — the generator knows the truth). All five spike trap classes present by construction
in seeded, reported proportions (abbreviations, false friends, GUID-shadow, cross-system
synonyms→WP10 multi-source, FK-comment→WP9.1 demotion) plus a wide-table fraction (100–300
cols) riding the width axis. Byte-deterministic for a fixed (tables, seed); keyless, depends
on vault_agent only for MAX_DOCUMENT_CHARS + normalize_identifier (eval→src direction).
(§3 usage capture) ForcedToolCaller gains an injectable usage_recorder (per-instance ctor arg
+ a module-level set_usage_recorder default, since the agents build their own callers) fired
once per API response with (model, input, output, cache_read) tokens — observational, no
behaviour change when unset, records even on truncation; eval/run.py registers a run-scoped
UsageTotals and writes usage + wall-clock + review-queue size (items and *rendered* line
count, the readability proxy) + construct/flag counts into each result JSON's new `metrics`
block, printed as a per-case summary. (§3 cases) eval/datasets.py EvalCase gains optional
profiling + a `generate:{tables,seed}` block (exactly one of input_document/generate);
materialize_case synthesises a generate case's inputs on demand into a temp workdir; run.py
feeds profiling to the mapper. scale_30 is committed (inputs == `generate --tables 30 --seed
42`, pinned) and gated loosely (mapping_accuracy≥0.8, pipeline_health=1.0); scale_100/scale_300
carry generate blocks and stay ungated (measurement). Findings template at
docs/architecture/scale-test-findings.md (run commands, budget/abort criteria). A first
candidate breakpoint was already observed (2026-07-18): the requirements_parser output cap
(max_tokens=4096) truncates on an inventory-heavy doc — the generator's requirements were made
leaner in response; confirming the exact breaking N (and chunking the parser like the contract
enricher) is the maintainer's first live task and a likely follow-up WP. 374 tests green (+21
in tests/test_scale_generate.py, +6 usage tests in tests/test_llm.py; two existing eval tests
updated for the new metrics key / shipped cases), ruff clean, mypy strict clean (35 files). The
core package gains no new dependency and no behaviour change when the usage recorder is unset.

WP14 column-based mapping coverage landed (as of 2026-07-19, eval-only,
docs/architecture/backlog-2026-07/wp14-scale-mapping-coverage-spec.md), fixing the scale gate
the first live WP13 run exposed (scale-test-findings.md Candidate #2): on scale_30,
mapping_accuracy scored 0.069 and failed its 0.80 gate 3/3 with a perfectly healthy pipeline
(pipeline_health 1.0, validation PASSED) — an eval-side artefact, not a mapper regression. The
mapper's concepts are the modeler's free-form hub-key/attribute names; the concept-keyed
mapping_accuracy matched them by normalize_identifier string-equality against the synthetic
golden's own sampled vocabulary, which diverges almost entirely at 30 tables (recall 1/28,
precision 1.00, ~50/51 proposals out-of-universe). NO src/vault_agent/ change (constraint of
the WP). EvalCase gains mapping_match: Literal["concept","column"]="concept": concept mode is
byte-identical (bank/messy_insurance, whose goldens are name-aligned — the WP9/WP9.2 scorer
tests pass untouched). column mode (the scale cases) swaps in two pair-based scorers in
eval/scorers.py: mapping_coverage (recall over golden mappable entries whose normalised
(source_table, source_column) pair is bound by some proposal — an ambiguous entry by any
candidate; no concept/entity coupling, no synthetic precision/F1, the statistics-trap GUID is a
different pair so it never covers the real key, out-of-golden-column proposals reported not
penalised) and false_friend_hits (1.0 unless a proposal binds a golden false_friends pair, then
0.0 — gateable, so the review gate "coverage ≥ 0.8 AND zero false-friend hits" is two min_scores
lines). gap_detection stays computed but reported-only in column mode (both its halves key on
the concept name → blind at scale; details prefixed "concept-coupled — reported only in column
mode"); load_eval_case rejects a column-mode case whose min_scores gates a concept-coupled
scorer (mapping_accuracy/gap_detection/confidence_calibration), attributable in the house loader
style. scale_30 re-gated to {mapping_coverage: 0.8, false_friend_hits: 1.0, pipeline_health:
1.0}; scale_100/scale_300 carry mapping_match: column, still ungated (measurement). Evidence:
eval/run.py writes state.mappings.model_dump() into every result JSON's new "mappings" key (added
only when supplied, so the payload-shape unit test stays byte-identical) — one scale re-run can
now be read concept-by-concept. The live re-run (spec §6: gate verdict now reflects mapping
quality; the dump confirms the naming-variant hypothesis) is the maintainer's remaining step.
388 tests green (+14: mapping_coverage full/partial/zero/GUID-trap/entity-blind/vacuous,
false_friend clean/hit, column-mode scorer set, gap reported-only, loader default+rejection,
payload dump), ruff clean, mypy strict clean (35 files).

WP14.1 crash-safe eval-run persistence landed (as of 2026-07-20, eval-only, findings
Candidate #3). The live post-WP14 scale_30 verification lost a completed, paid-for repeat
1/3 when the credit balance ran out during repeat 2/3 (Anthropic 400, correctly non-retried
by ForcedToolCaller): eval/run.py wrote all result JSONs only after the whole batch. The run
loop is restructured into _run_score_write, which writes each repeat's JSON (scores + metrics
+ mappings dump) via _write_one_result the moment that repeat is scored — so an exception in
run_case_once returns (failed_repeat, reason) with every completed repeat already on disk;
main() renders the summary from the completed repeats, prints a "BATCH INCOMPLETE: … n/m
run(s) completed and saved" banner, exits non-zero, and stops (a fatal 4xx like an exhausted
balance stays fatal — no re-attempt of remaining --all cases). Only run_case_once is guarded;
the deterministic score/write step is not. Success path unchanged: identical JSON shape,
filename scheme, and console output for a fully green batch. No src/vault_agent change. 390
tests green (+2 keyless via a stubbed run_case_once/_score_run/run_metrics seam: run-2 failure
leaves run 1 persisted + returns the failure marker; success writes every repeat), ruff clean,
mypy strict clean.

WP15 LLM trace capture landed (as of 2026-07-22,
docs/architecture/backlog-2026-07/wp15-trace-capture-spec.md; origin: Karpathy LOOPS.md rule VII
"read the traces"). The pipeline's LLM interactions are no longer invisible after the fact:
llm.py gains a TraceEvent frozen dataclass (kind llm_call/llm_error/backstop, tool_name, model,
attempt, system_prompt + system_prompt_sha, user_content, max_tokens, payload, stop_reason,
usage numbers, error, and the WP16 backstop_id/detail) plus a recorder seam mirroring WP13's
usage recorder exactly — module-level set_trace_recorder(...) (the CLI/eval harness sets it,
library code never does) with a per-instance ForcedToolCaller ctor arg for tests, and an
emit_trace(event) helper whose recorder exceptions are swallowed with a warning (observational,
never fatal). Emission: every completed API response (including a truncated one — usage
semantics) and every terminal failure (truncation, missing tool block, exhausted retries, and —
beyond the spec's §2.1 list, added after a live run hit it — a propagating non-retryable 4xx
such as an exhausted credit balance); a retryable attempt that will be retried is NOT an event.
Writer: src/vault_agent/trace.py JsonlTraceWriter appends one JSON object per event (ISO
timestamp + all fields), writing the system prompt in full on the first event per sha and by
sha alone afterwards (the modeler's prompt is byte-identical across retries by WP3 design);
opened in append mode per event, so a resumed run continues ONE transcript and a crash keeps
what was written. CLI: `run`/`resume` register the writer at
<out>/.vault-agent/traces/<thread_id>.jsonl via a _tracing() contextmanager (always cleared in
finally), **default ON** with `--no-trace` to opt out; the interactive checkpoint threads the
flag into its in-process resume. Eval: each repeat's trace lands next to its result JSON as
<timestamp>-run<N>.trace.jsonl (the timestamp is now stamped before the run so both share the
stem) and metrics gains trace_path; scale-test-findings.md gained the protocol line — quote the
trace (tool_name/attempt), don't file hunches. Traces are debug artifacts, not deliverables:
timestamped (exempt from the byte-identity rules), carrying raw document/source text, hence
.vault-agent/-only, git-ignored, and README-flagged as not demo-safe. Verified live 2026-07-22
against the real API path (the failing requirements_parser call landed in the jsonl with tool
name, model, attempt and full system prompt); acceptance #1's full `grep emit_dv_model`
payload demo was CLOSED 2026-07-27 (see the verification-batch paragraph below).
21 keyless tests (+6 tests/test_trace.py, +7 in test_llm.py incl. the raising-recorder and
instance-override paths, +4 CLI: trace file per thread, resume appends, --no-trace writes
nothing, flag exposed).

WP16 steering registry, backstop telemetry and the model-release re-test landed (as of
2026-07-22, docs/architecture/backlog-2026-07/wp16-steering-retest-spec.md; origin: LOOPS.md
rule VIII "delete the harness"). Parts of the harness are model-compensation (the CDK line
landed only after steering failed 4/4, plus a deterministic backstop) and nothing could answer
"does the next model still need this?". Now: (§2.1) DV_MODELING_RULES is list[SteeringRule]
(frozen dataclass: id, text, backstop, origin) — the rendered modeler prompt is BYTE-IDENTICAL
to pre-WP16, pinned against a fixture generated from the old constant
(tests/fixtures/steering/modeler_rules_pre_wp16.txt). (§2.2) active_modeling_rules() honours a
module-level exclusion set (set_excluded_rules(ids|None), unknown id raises attributably,
None = identity); production code NEVER sets it — the seam exists for eval/ablate.py.
(§2.3) The three pre-gate backstops emit TraceEvent(kind="backstop") through the WP15 seam when
and only when they actually repair something: attributes_without_cdk (modeler CDK dedup),
fk_demotion (WP9.1 source_mapper), effsat_two_attributes (code generator's !=2-attributes
rejection; the GENERATION_GAP flag stays the human channel, the event adds counting).
eval/run.py counts them per repeat into metrics.backstop_fires via a BackstopCounter fanned out
alongside the trace writer. (§2.4) eval/ablate.py (`python -m eval.ablate --case <c> --drop
<rule_id> [--model <id>] [--repeat N]`) runs baseline vs. rule-dropped arms on the real graph
(reusing run_case_once/_score_run), recording scores, validation issue codes, backstop fires
and usage per arm, with WP14.1 crash-safety (the comparison JSON under eval/results/ablation/
is rewritten after EVERY completed repeat) and a printed two-column summary. (§2.5)
docs/architecture/steering-ledger.md holds the full inventory (15 modeler rules + the two
source_mapper prompt heuristics, which stay in their prompt file and are manual-ablation only)
and the release protocol: on a model bump, ablate gated cases × backstopped rules first; zero
backstop fires AND no gated-score regression over N>=3 repeats makes a rule candidate-delete —
a human decides, prompt text is cheap to revert, deleting a backstop needs the evidence AND its
E_-gate kept. Scope boundary stated everywhere: validator gates are the product, never ablated,
never deleted here. Acceptance #2 (a live cdk_not_payload ablation on health_insurance) was
CLOSED 2026-07-27 (see the verification-batch paragraph below). 433 tests green (+15 tests/test_steering.py: id uniqueness,
byte-identity, exclusion/clear/unknown-id, backstop-link consistency, the three telemetry sites
firing only on a real repair, no-recorder no-op; +8 tests/test_eval_ablate.py: both arms, report
shape, arm-2 failure persistence + seam always cleared, summary/render helpers), ruff clean,
mypy strict clean (37 files).

Live verification batch (2026-07-27/28), executed once API credit existed — it closes the three
measurement items WP14/WP15/WP16 had to leave open and produces one eval fix plus two recorded
findings. (1) WP15 acceptance #1 CLOSED: a real `vault-agent run` on the bank demo wrote one
grep-able transcript per thread; `grep emit_dv_model` finds the modeler call on claude-opus-4-8
with the FULL payload (3 hubs, 2 links, 4 satellites incl. multi_active + effectivity), its
system prompt (sha 21e230df28dd70e2), stop_reason and token counts. The pause+resume half is
weaker than the spec assumed and the spec wording should be read accordingly: a resume produces
NO new events because every post-checkpoint node (adr_author) is deterministic, so "appends to
the same file" is today only verifiable as "continues the same file, creates no second
transcript" — appending on resume is structurally unreachable until an LLM call moves behind the
checkpoint. (2) WP16 acceptance #2 CLOSED, and the LOOPS rule-VIII answer for cdk_not_payload is
KEEP: `eval.ablate --case health_insurance --drop cdk_not_payload --repeat 3` fired the
attributes_without_cdk backstop 0× in the baseline arm and 4× (2/1/1) in the dropped arm, plus
W_MASAT_SHARED_GRAIN ×3 there — i.e. the prompt line alone now suffices, and without it the
model reverts to the July behaviour and only the deterministic backstop keeps the output correct.
Scores are indistinguishable between arms (construct_f1 0.566 vs 0.576, both gates 1.0), which
is the point of the telemetry: the backstop hides the regression from the scores. (3) WP14 §6
CLOSED: a live scale_30 re-run scores mapping_coverage 1.00 (28/28 golden pairs bound),
false_friend_hits 1.00, pipeline_health 1.00 — all three gates pass, so the gate verdict now
reflects mapping quality instead of the 0.069 concept-naming artefact of 2026-07-19. Run
metrics: 40 calls, 64,066 in (cache-read 238%), 78,229 out, 849.8 s, 97 review items / 53
rendered lines.

Two findings from that batch. (F1) WP13 candidate #1 is CONFIRMED and sharper than recorded:
scale_30 repeat 2/3 died with `LLMCallError: emit_requirements: response truncated at
max_tokens=4096`. The generate case is byte-deterministic for a fixed (tables, seed), so the
input was identical to the repeat that passed — at 30 tables the requirements_parser sits ON the
output cap and sampling variance decides. A flaky breakpoint, not a clean one; FIXED in the
paragraph below (2026-07-28). WP14.1 behaved as
designed: repeat 1 was already persisted when repeat 2 died, so the batch is INCOMPLETE (1 of 3)
and the gate verdict above rests on a single measurement. (F2) An eval-scorer defect found by
reading the ablation traces, fixed here (eval/ only, no src/vault_agent change): link matching
keyed on `normalize_identifier(link.name)`, which folds casing and separators but NOT word
order. The modeller named the same construct `link_policy_insured_person` where the golden says
`link_insured_person_policy`, so a DV-correct model scored links F1 0.29 and driving_key_accuracy
0.00 in all six ablation runs — the model was right, the scorer was wrong. eval/scorers.py gains
_link_grain() (the sorted MULTISET of normalised participating hubs, ADR-0009 roles collapsed to
their hub — a multiset so a self-referencing link stays distinguishable from a single
participation) and _resolve_link(), shared by _matched_links and driving_key_accuracy: a golden
link resolves on grain, and the NAME only breaks a tie between two generated links of the same
grain (the W_LINK_REDUNDANT_GRAIN case); an unresolvable tie stays unmatched rather than guessed.
Re-scoring the six recorded models lifts driving_key_accuracy 0.000 → 1.000 in every run and
construct_f1 from 0.566/0.576 to 0.698/0.767 per arm (indicative: computed from the raw
emit_dv_model payload, not the post-backstop state). Behaviour is byte-identical wherever golden
and modeller agree on the name — the 18 pre-existing scorer tests passed untouched. This is the
THIRD instance of the same class after WP9.2 and WP14 (eval scoring free-form LLM names instead
of structure), so the caveat is now written down rather than rediscovered: hubs and satellites
are STILL name-keyed (eval/README.md states this explicitly), which is safe only for the
hand-written cases and is one reason the scale_* cases gate on mapping scorers.

Also recorded, NOT fixed: `_f1` treats an empty golden inconsistently — with no golden constructs
declared, construct_f1 returns 0.0 (matched==0) while driving_key_accuracy returns 1.0 ("no
golden driving keys declared"). Both mean "nothing to check", with opposite answers; this is why
the scale_30 result JSON reads construct_f1 0.000 (`hubs: 0/0 golden matched, 17 generated`)
although the synthetic cases carry a golden MAPPING and no golden MODEL at all. Not a quality
signal — do not read it as one. 437 tests green (+4 in tests/test_eval_scorers.py: reversed name
component order matches, self-reference grain stays distinguishable, ambiguous grain resolved by
name, unresolvable tie stays a miss), ruff clean, mypy strict clean (37 files).

The requirements-parser breakpoint (F1 above) is fixed and live-verified (2026-07-28). Two levers,
both aimed at the OUTPUT — which is what overflows — not the input. (1) _MAX_TOKENS 4096 -> 8192,
matching the contract enricher; output tokens are billed per generation, so the headroom is free.
(2) Adaptive segmentation in agents/requirements_parser.py: the whole document is tried first and
ONLY a truncated response triggers a split, so every document that already fits keeps making
exactly one call with unchanged content (pinned by test — the segmentation is invisible until
needed). split_document() halves the text at the best structural boundary nearest the midpoint
(markdown heading, else blank line, else newline), so a segment is always a whole number of
structural units and a requirement is never severed mid-sentence; recursion is bounded by
_MAX_SPLIT_DEPTH=4 (up to 16 segments) and by an unsplittable segment, which re-raises. A FIXED
CHARACTER THRESHOLD WOULD HAVE BEEN THE WRONG PROXY and this is the reason to keep the adaptive
shape: messy_insurance is LARGER (4,511 chars) than the 30-table scale document (3,727) yet yields
~34 requirements instead of ~100 — output tracks content DENSITY, not length, so any threshold
that split the scale case would also have split a case that never needed it. llm.LLMCallError
gains a typed `truncated` attribute (set on the stop_reason == "max_tokens" path) so the parser
branches on the cause, never on message text (the P1 rule); a missing tool block still propagates
unsplit. merge_records() folds the segments: each call numbers from scratch, so content-identical
records (same text + category, seen twice across a cut) are dropped and colliding ids get a
deterministic -2/-3 suffix — both no-ops for a single segment. New FlagKind.INPUT_SEGMENTED tells
the human the document was split (advisory; deliberately NOT in REVIEW_FLAG_GROUPS since it fires
once per document, same as INPUT_TRUNCATED). Live proof on a generated 100-table document (9,027
chars, 93 bullets), every branch exercised once: call 1 over the whole document returned
stop_reason=max_tokens with 8,192 output tokens and an empty payload; the split produced 6,015 +
3,012 chars (lossless); calls 2 and 3 returned 88 and 47 records at 7,025 / 4,055 output tokens;
the merge resolved 47 real id collisions (both segments emitted REQ-001…) into 135 requirements
with zero duplicate ids, and the INPUT_SEGMENTED flag was raised. Cost of the adaptive shape,
stated plainly: the triggering call burns its full output budget for nothing (~$0.12 of the
~$0.31 probe) — paid only by documents that would otherwise fail outright. NOTE the live scale_30
re-run (2026-07-27, 1 repeat) is NOT evidence for this fix: it emitted 3,591 output tokens, below
even the old 4,096 cap, so it would have passed unfixed — it confirms the new cap is in effect and
that the WP14 gates hold on a second independent measurement (mapping_coverage / false_friend_hits
/ pipeline_health all 1.00, 40 calls, 856 s), nothing more. 446 tests green (+9 in
tests/test_agents/test_requirements_parser.py: boundary priority, lossless split, indivisible
document, merge identity for one segment, id de-collision + duplicate drop, one-call regression
guard, truncation→split→merge, non-truncation error propagates unsplit, indivisible truncation
propagates), ruff clean, mypy strict clean (37 files).

Output-budget hardening across the pipeline (2026-07-28), driven by three live scale_100
attempts. STATUS FIRST, so nobody reads more into this than it says: **scale_100 has never
completed end to end.** Each attempt died one agent further along, and the axis is verified
at 30 tables only — do not read "the scale cases exist" as "100 tables works". What IS live-
proven at 100 tables: the requirements-parser segmentation, the business-key segmentation,
and the modeler at 16384. What is keyless-tested ONLY: the source-mapper segmentation (it
has never run against the real API). The class behind all of it: an agent whose OUTPUT
scales with the landscape while its budget is fixed. Sites, in the order they surfaced:
emit_requirements (fixed 2026-07-28, above), emit_business_keys (was the last agent still at
4096 while the other four sat at 8192), emit_dv_model, emit_mapping.

Two shapes, and the difference decides the fix. A LIST-shaped output (requirements,
business keys, mapping decisions, contract fields) can be SPLIT: the mechanism is
llm.call_with_truncation_split() — try the whole unit, halve it only on
LLMCallError.truncated, bounded by MAX_SPLIT_DEPTH=4 — with merging left to each agent
because identity is domain knowledge (requirement ids collide across segments, business keys
collide on (entity, field), mapping decisions on the concept). A failing branch
short-circuits its sibling: a partial result that silently dropped half the input would be
worse than a loud failure. The source mapper adds one asymmetry worth keeping in mind — only
the CONCEPTS are split, never the schema, because a concept can only be mapped against the
whole candidate column set. A SINGLE-ARTEFACT output cannot be split: the modeler emits one
coherent model, and merging two half-models is a modelling problem (a link can span the
halves, a hub proposed in both must be reconciled, a satellite's parent can sit on the other
side), so the budget is the only lever there.

Numbers to reason with, all measured rather than guessed. Modeler output: 30 tables ->
7,225 tokens, 100 tables -> 13,889 (isolated replay) and 14,981 (in-pipeline) — sub-linear
growth, 3.3x tables for ~1.9x tokens, extrapolating to ~26k at 300 tables. At 8192 the
30-table case was already at 88%, so the 100-table failure was overdue, not surprising.
16384 is the ceiling that is safe WITHOUT streaming (ForcedToolCaller is non-streaming;
above roughly that size non-streaming requests risk HTTP timeouts), and at 91% in-pipeline
utilisation it is a stopgap: 300 tables needs streaming in ForcedToolCaller or staged
modelling (hubs, then links, then satellites). Peak-output-against-cap at 100 tables, the
table to re-run before the next attempt rather than rediscovering serially:
emit_requirements 100% (splits), emit_mapping 100% (splits), emit_business_keys 97%,
emit_dv_model 91% at 16384, emit_contract_enrichment 61%. METHOD NOTE, recorded because it
cost real money: three attempts at ~$5 each went into finding these one at a time, when
every number was already sitting in the traces on disk. After the second failure, "next
agent, same failure class" was a pattern, not a coincidence — audit the whole pipeline's
utilisation from the existing traces before paying for another run.

Also in this batch (eval only): a scorer with nothing to check is now vacuous rather than
failing. construct_f1 returned 0.000 for the synthetic scale cases — they ship a golden
mapping and no golden model — because _f1 scored matched==0 as total failure; it now means
over the kinds the golden actually declares, names an undeclared kind in details, and a
wholly empty golden reports 1.0 with a "vacuous —" prefix like driving_key_accuracy.
Swapping a misleading 0.000 for a misleading 1.000 would be no fix, so load_eval_case
REJECTS a case gating either scorer when the golden declares nothing for it (the gate would
pass on absence of evidence), and eval.run's render_table marks a vacuous scorer inline
since the console shows only mean/min/max. This also sharpened the existing pins rather than
loosening them: every single-kind golden had been diluted by free 1.0s from the kinds it
never declared, so a total miss scored 2/3 — and
test_construct_f1_zero_when_golden_expected_but_nothing_generated now matches its own name.
465 tests green, ruff clean, mypy strict clean (37 files).

WP18 eval gate integrity landed (as of 2026-07-28, eval/ only, no src/vault_agent change;
docs/architecture/backlog-2026-07/wp18-eval-gate-integrity-spec.md), closing the last two
holes of the "a gate passes on absence of evidence" class after WP9.2, WP14 and the
vacuous-_f1 fix. (§2.1) A gated scorer that produced NO score — a typo in min_scores, or a
case whose golden_mapping.yml is missing, which makes _score_run skip the entire mapping
family — used to disable its gate silently and exit 0; eval.run.unsatisfiable_gates (pure,
reported before any score verdict) now prints `GATE UNSATISFIABLE: <name> is gated but
produced no score …` to stderr and exits 1. It is deliberately separate from failed_gates:
a batch defect must never be reported as a failed score. It is skipped when ZERO repeats
completed, where every gate is trivially unscored and the WP14.1 BATCH INCOMPLETE line
already states the cause. (§2.2) One vacuity convention for every scorer, single-sourced as
scorers.VACUOUS_PREFIX ("vacuous — "): nothing to check ⇒ score 1.0 AND details starting
with the prefix. mapping_accuracy / mapping_coverage / false_friend_hits / gap_detection
gained it (in column mode the marker composes FIRST, the reported-only note after, so the
startswith key holds), and confidence_calibration's polarity was inverted — it scored
"no scored proposals" as 0.0, the pre-fix construct_f1 defect mirrored. construct_f1 /
driving_key_accuracy keep their exact wording, now via the shared constant. (§2.3) A vacuous
score can never satisfy a gate: the loader keeps its cheap early rejection for the model
scorers, and the runner adds the check the loader structurally cannot make — the golden
mapping is a separate file load_eval_case never opens — so a gated scorer that was vacuous
in EVERY repeat is also GATE UNSATISFIABLE, exit 1. false_friend_hits now distinguishes a
real clean bill of health ("N false-friend column(s) watched") from "none were declared".
eval.ablate carries no min_scores gate and pinned no vacuity text, so only the details
strings reach it. Deliberately changed pins: none needed updating — the four vacuity
branches were unpinned and confidence_calibration's 0.0 was untested, which is how it
survived. Acceptance #1 (deleting scale_30's golden_mapping.yml makes the runner exit 1)
is NOT verified: the gate check runs after scoring, so the check costs a full live run —
and, as the kick-off anticipated, the LLM calls come first. 474 tests green (+9: two
unsatisfiable_gates unit tests, three main-level exit-code tests via a keyless stub seam,
the cross-scorer convention test incl. vacuous_scorers pickup, gap_detection prefix order,
false-friend non-vacuous, confidence_calibration polarity regression), ruff clean, mypy
strict clean (37 files).

WP19 put the LAST list-shaped agent on the shared truncation split (as of 2026-07-28,
docs/architecture/backlog-2026-07/wp19-contract-truncation-split-spec.md). data_contract
was the remaining site where a fixed width assumption could kill a run at the third
pipeline stage: the enricher pre-chunked at _FIELDS_PER_CALL=40 and its own arithmetic
(~200 output tokens/field ⇒ ~8,000 of the 8,192 budget) claimed that "keeps a full chunk
well under" the cap — the review falsified it, and a denser-than-assumed chunk raised
LLMCallError(truncated) with no recovery. Both layers are kept, deliberately: the
pre-chunking stays as the cheap FIRST-ORDER bound (a known-wide table never pays a doomed
full-budget probe call), and each unit now goes through llm.call_with_truncation_split
(unit = the chunk's field list, split = exact halving via the new data_contract.split_fields,
None at a single field; merge = the existing _merge_enrichment, which already folds fields
across an asset's chunks). An indivisible single field that still truncates re-raises, and a
non-truncation LLMCallError propagates unsplit — both the shared helper's contract, pinned
here too. When any chunk of an asset had to split, ONE advisory FlagKind.INPUT_SEGMENTED
flag is raised for that asset (asset = the asset name, message naming chunk and segment
counts); deliberately NOT added to REVIEW_FLAG_GROUPS, so it stays individually visible like
the parser's per-document flag. The system prompt stays byte-identical across every call
(WP3 caching), and a run where nothing truncates makes exactly the same calls with the same
payloads as before — pinned, together with the two pre-existing batching tests, which passed
untouched. 478 tests green (+4: truncated chunk → halves → full field coverage + flag,
non-truncation error propagates after exactly one call, indivisible truncation re-raises,
no flag when nothing truncates), ruff clean, mypy strict clean (37 files).

WP20 closed the trust gap between report.py and the write path (as of 2026-07-28,
docs/architecture/backlog-2026-07/wp20-name-gates-spec.md, review findings 4+5). report.py
treats every state string as hostile; cli.write_outputs did not — it built
`models_dir / f"{name}.sql"` and `contracts_dir / f"{asset}.contract.yml"` straight from
LLM-derived names, so a name carrying a path separator or `..` would have written OUTSIDE the
output directory, and a name with spaces or uppercase produces dbt models that cannot be
ref()'d. Four changes, all deterministic. (§2.1) A new validator gate E_BAD_NAME (error) on
every hub/link/satellite name, against rules.CONSTRUCT_NAME_PATTERN
(^(hub|link|sat)_[a-z0-9][a-z0-9_]*$) + is_valid_construct_name() — one source of truth in
rules/, message naming the offending characters. It blocks BEFORE generation, so the re-model
loop fixes it (the E_SAT_DUP_ATTR pattern). Validator codes are now 33 (22 E_/11 W_; the code
stays the source of truth — the docstring said 30 while the ops catalogue said 32, both are
now 33). (§2.2) A DELIBERATE prompt change: SteeringRule construct_naming (backstop=None —
a gate refuses, it does not repair) so a deterministic formality never burns a modeling
retry. That makes the registry 16 rules, so tests/fixtures/steering/modeler_rules_pre_wp16.txt
was updated in the same commit — the pre-WP16 block is still a byte-identical PREFIX of the
file (asserted while regenerating), the test comment now records the addition, and the
steering ledger carries the new row. (§2.3) write_outputs gains cli._safe_component: every
filename component derived from state (raw-vault models, staging models, contract assets,
contract tests, ADR filenames) is rejected with an attributable ValueError when it holds a
path separator, `..`, control characters, or is blank. It REFUSES, never renames — a
sanitised name would silently disagree with the ref() inside the generated SQL. With §2.1
upstream this is unreachable for constructs; contract asset names, which pass no such gate,
are the reason it exists. (§2.4) The two staging-name paths are unified on
normalize_identifier(base).lower(): staging_generator._staging_name and
code_generator._staging_model now normalise the way _sat_staging_model already did (which in
turn just calls _staging_model). Byte-identical for every well-formed name — the ungrounded
staging baseline fixture and the bank demo guardrails pass untouched. (§2.5)
E_SAT_ATTR_OVERLAP keys on the NORMALISED attribute like E_SAT_DUP_ATTR, so "Customer ID" in
one satellite and customer_id in another satellite of the same parent — one generated column
on that parent — is now the error it always was; both original labels are reported, and the
single-label message is byte-identical to before. Docs updated in the same commit
(08-validation-gates catalogue + count, dv2-rules cheatsheet, and one 02-concepts example
that used an `eff_sat_` name the new gate rejects). 487 tests green (+9: clean model has no
name issue, four malformed names caught with the offending character named, normalised
overlap across satellites, disjoint attributes stay clean, three write-guard refusals with
nothing written outside out_dir, the steering rule's registry/ledger pins), ruff clean, mypy
strict clean (37 files).

WP17 gave the CLI the crash safety the eval harness got in WP14.1 (as of 2026-07-28,
docs/architecture/backlog-2026-07/wp17-cli-crash-recovery-spec.md, review finding 1). Until
now ANY node raising after expensive LLM work threw everything away: _run_pipeline
propagated, write_outputs never ran, no pending.json was written, and `resume` refused —
while the completed nodes sat in checkpoints.sqlite under a thread_id printed nowhere. Now:
(§2.1) pending.json carries phase "paused" | "crashed" (+ an `error` summary when crashed);
the shape stays dict[str,str] and a pre-WP17 file without the key reads as paused (pinned).
(§2.2) A crash triggers a RESCUE inside the saver block: record the crashed pointer — that
pointer is what makes the thread reachable at all — then load the thread's latest checkpoint
and write the artifacts-so-far, then RE-RAISE. Every rescue step is individually guarded and
its failures are logged, never raised: the user must see the exception that actually killed
the run, not one from the recovery (pinned by a test that breaks the checkpoint read). The
thread is deliberately NOT deleted, and --no-write is honoured (pointer only). (§2.3)
`resume` continues a crashed run with ainvoke(None) on the same thread — VERIFIED against
the installed langgraph 1.2.4 rather than assumed (the WP8 t_link lesson): LangGraph resumes
from the latest checkpoint and re-executes ONLY the failed node, so completed agents are not
paid for twice (pinned: code_generator runs once across the crash+continue). If the continued
run reaches the HITL checkpoint it becomes a paused run and is handled exactly as `run` does
— decision flags apply immediately, a TTY prompts, a pipe prints the instructions; it never
decides for a human who has not seen that checkpoint yet. New `resume --discard` drops thread
+ pointer for a run not worth continuing. (§2.4) At `run` start, threads pending.json does
not reference are pruned — the SIGKILL class that never reaches an except-branch, i.e. the
unbounded growth WP5 §5.5 fixed, reintroduced through the crash path. Listing uses the
documented aiosqlite `conn` (verified against langgraph-checkpoint-sqlite 3.1.0); any failure
skips pruning silently, because hygiene must never be why a run cannot start. Internally the
three invocation paths (run / resume-with-decision / continue-crashed) are now ONE
_invoke_checkpointed with the crash rescue in it, and _paused_state shares
_state_from_checkpoint with the rescue. One honest limit: `run` only advertises recovery when
a crashed pointer actually exists — a failure before the checkpointer opened (a bad input
file) promises nothing, since there is nothing to continue. Docs updated in the same commit
(operations 03/06/10/12: crashed phase, --discard, single-slot pending, orphan pruning, the
new troubleshooting rows). 497 tests green (+10, all keyless against the stub graph but the
REAL sqlite saver in tmp: crash writes pointer+artifacts and keeps the thread, cross-connection
continuation finalises and prunes, crash→checkpoint pauses, flags applied after a
continuation, no-flags non-TTY reports instead of deciding, --discard, rescue never masks,
orphan pruning spares the pending thread, pause-path phase regression + legacy phase-less
pending, no false recovery promise), ruff clean, mypy strict clean (37 files).

WP21 robustness + hygiene batch landed (as of 2026-07-28,
docs/architecture/backlog-2026-07/wp21-robustness-hygiene-spec.md, review findings 6+7a–f),
one behaviour fix and six cleanups. (§2.1) An unreadable document no longer kills a run:
_read_document flagged-and-skipped an unsupported EXTENSION but let a Latin-1 .md
(UnicodeDecodeError), a corrupt PDF (pypdf) or a broken .docx propagate — against the
module's own contract. All three extraction branches are now wrapped; the catch is
deliberately broad (`except Exception`, commented) because pypdf's and python-docx's
exception surfaces are not a stable API, and the failure becomes an error flag
(MISSING_INPUT, asset = the path, message naming the exception type) plus a skip, so one bad
file in a multi-document run does not take the run down. (§2.2) The usage recorder is
guarded like emit_trace — its docstring promised "never disturbs the call path" while having
no try/except, and the response is already BILLED when it fires, so a broken accounting sink
discarding it was the most expensive failure mode available. (§2.3) A collapsed review line
derives its `source` from its members (one distinct source, else "multiple agents") instead
of the hardcoded "data_contract" — the aggregatable groups come from three different agents,
and the wrong name sends a reviewer to the wrong artifact. Rendering is unchanged in shape:
md and the HTML report both print the derived source (the CLI checkpoint never printed a
source, which stays as it was — no per-renderer logic was added). (§2.4) The validator
docstring drops its literal gate count; the module already declares the code the source of
truth, and the literal had been wrong twice. (§2.5) The WP10 multi-source satellite branch
now emits _collision_warnings once per satellite, parity with _render_satellite, which it
skipped by `continue`-ing. (§2.6) A dropped invalid construct carries its `name` as the
flag's asset when the record still has a usable one — every other DROPPED_RECORD names its
construct — and stays unattributed rather than inventing one when it does not. (§2.7)
--no-write is decided and documented as ARTIFACTS-ONLY: run state (checkpoint, pending,
trace) is always written, or a paused --no-write run would be unresumable. `resume` gains the
matching --write/--no-write, both help texts state the scope, and a pause reached under
--no-write warns that the printed resume WILL write unless --no-write is repeated. Docs:
operations 06 (flag scope, resume, unreadable documents) and 12 (new troubleshooting row).
The report fixture needed no regeneration — it carries no collapsed group, verified rather
than assumed. 509 tests green (+12: three unreadable-document cases via parametrize, raising
usage recorder, single- and multi-agent collapsed source, renderer parity for the derived
source, one collision flag on the multi-source path, dropped-record asset present/absent,
--no-write pause stays resumable + warns, resume --no-write finalises without artifacts),
ruff clean, mypy strict clean (37 files).

WP24 multi-source composition correctness landed (as of 2026-07-29,
docs/architecture/backlog-2026-07/wp24-multi-source-composition-spec.md, review findings
2+3) — the only defect class in this project that produced wrong **data** rather than a
wrong message. WP7 (satellite source_table), WP8 (role-qualified links) and WP10
(multi-source hubs) were each correct and each tested; two of their pairwise combinations
were not. Why the suite was blind to it, stated plainly because it is the lesson: EVERY
existing multi-source test and the WP10 Postgres verification used the *disagreeing*-feed
case, where canonical_hub_key_column() happens to return normalize(business_key) — so a
call site that ignored the helper entirely produced identical output and no test could
tell. The agreeing-feed case (feeds share a physical column name that differs from the
business-key label) is where the helper earns its existence, and nothing exercised it.
(§2.1) rules.canonical_hub_key_column() is the declared single source for a hub's staging
key column but only 2 of its 5 call sites used it; the other three — link participations,
a source_table satellite on a hub parent, and one on a link parent — read
_to_column(hub.business_key) and so staged CUSTOMER_ID where the hub staged CUSTOMER_KEY:
same target column, different hash input, an FK that can never join its hub. All three now
route through the helper; role qualification composes on top
(role_bk_column(canonical_hub_key_column(hub), role)), and the single-source path is
unchanged by construction (the helper returns normalize_identifier(business_key) with no
sources), which the untouched staging baseline fixture + bank/mapping demo guardrails pin.
(§2.2) The WP7×WP10 combination — a satellite declaring source_table on a hub declaring
sources — emitted a dbt project that CANNOT build (per-source satellites reading
stg_<entity>_<source> while the hashdiff they reference is computed only in an orphaned
stg_<sat base>), with zero flags. It has no defined semantics: one finer-grain relation
cannot be the payload source of two feeds whose rows are told apart by record_source.
Rejected now in three agreeing places, all asking ONE predicate
(rules.source_table_on_multi_source_hub, deliberately in rules/ so validator and both
generators cannot drift): validator gate E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB (error, so
it blocks BEFORE generation and feeds the re-model loop — the E_SAT_DUP_ATTR pattern),
FlagKind.GENERATION_GAP from the code generator, and the staging generator skipping the
satellite too, so no orphan model is left behind. Validator codes are 34 (23 E_/11 W_; the
code stays the source of truth). NB the gate was specced as E_MASAT_MULTI_SOURCE_PARENT and
renamed during implementation — it does not check multi-active, it checks source_table ×
multi-source parent and fires for any non-effectivity satellite type (effectivity sats
ignore source_table by design); spec + kick-off carry the correction. (§2.3) The deliverable
is the matrix, not the two fixes: tests/test_agents/test_feature_composition.py exercises
all 8 WP7×WP8×WP10 cells with the expected outcome per cell in its docstring (cell 6 is the
one deliberately "flagged, not generated"), plus the invariant that catches this whole
class — across ALL staging models of one DV model, a target column must be hashed from
exactly ONE input set — run over every model the suite builds elsewhere (both demo
builders, the mapping demo's grounded model, the WP8 and WP10 fixtures), not just the new
cells. Verified by mutation: with the src changes stashed, 8 of the new tests fail
(including the invariant on all four multi-source cells); with them, all pass. A Postgres
re-verification was NOT required and not performed — no rendered template changed for the
single-source path, and the corrected multi-source staging is exercised structurally.
541 tests green (+32: the 8-cell matrix, the invariant over 14 models, canonical link FK,
canonical role-qualified FK, sat-on-link-parent canonical hash, the rejected cell's
gate+flag+no-sat+no-orphan-staging, WP7-alone still generates, and 6 parametrized predicate
cases incl. the effectivity exclusion), ruff clean, mypy strict clean (37 files). Docs:
operations 08 gate catalogue (count + new row) and the dv2-rules cheatsheet.

WP26 ADR completeness landed (as of 2026-07-29,
docs/architecture/backlog-2026-07/wp26-adr-completeness-spec.md, review finding 4). The
generated ADR is the pipeline's human-facing architecture record, and it omitted most of
what WP7-WP10 taught the model to express: driving keys were not rendered AT ALL (while
this file claimed they were — that claim is now true rather than corrected), a hub
integrating two source systems read exactly like a single-source hub, a multi-active or
effectivity satellite was indistinguishable from a standard one, and the ratified
business↔source mappings lived only in mappings.review.yml. The agent stays LLM-free —
every addition is a projection of typed state, which is what makes the record
non-hallucinated. (§2.1) Hub lines carry the feeds plus the canonical staging key column
read from rules.canonical_hub_key_column (never re-derived — the ADR must name the column
staging actually builds, WP24's lesson applied to the renderer); link lines carry the
driving key through Link.resolve_driving_refs(), rendered by the SAME helper as the
participation list so a reader comparing the two lines needs no translation, with
unresolvable entries silently absent (E_DRIVING_KEY_NOT_IN_LINK owns that complaint);
satellite lines carry non-standard sat_type + child_dependent_key and the WP7 source_table.
Beyond the spec's list: the transactional link's payload/event timestamp, because
link_type selects automate_dv.t_link and acceptance #1 demands that anything changing what
is BUILT is either visible or listed as omitted — the deliberate omissions (Hub.source_entity,
a proposal's confidence/evidence, the data contracts) are now enumerated in the module
docstring rather than left implicit. (§2.2) A conditional Source mappings section renders
proposals (concept → TABLE.COLUMN, category, ratification status), gaps and unresolved
concepts; absent entirely when the mapper was inert, so an ungrounded ADR is byte-identical.
A gaps-only run still gets the section — a gap is first-class output (ADR-0008 #3), not an
absence of one. (§2.3) The determinism claim is made TRUE by making it precise instead of
by removing the date: byte-identical for a given state AND date, `today` injectable,
defaulting to the clock, which is correct for a dated decision record; docstring, the WP2
paragraph above and the (renamed, extended) determinism test now agree. Guard: the three
construct renderers are module-level one-line-per-construct functions so WP23's delta-ADR
can render a SUBSET without forking the formatting, and a pre-WP26 fixture
(tests/fixtures/adr/adr_pre_wp26.md) pins the additions as strictly additive — it was
generated from the OLD renderer with the src changes stashed, so it proves compatibility
rather than merely self-consistency. 551 tests green (+11: the byte-identity fixture,
multi-source feeds, canonical name from the helper on agreeing feeds, role-qualified
driving key matching the participation list, unresolvable driving key absent, sat
type+CDK+source_table with standard staying silent, transactional link, no section when
ungrounded, full mappings section, gaps-only section, extended determinism), ruff clean,
mypy strict clean (37 files).

WP25 made a failed run a first-class outcome (as of 2026-07-29,
docs/architecture/backlog-2026-07/wp25-failed-run-outcome-spec.md, review finding 1),
closing the last place where the product's self-assessment and its externally visible
behaviour contradicted each other. A model that never validated ended the run as a SUCCESS:
route_after_validation sent an exhausted re-model budget to END, so the CLI printed
"requires sign-off", wrote review-queue.md saying **requires sign-off**, wrote no ADR, wrote
no pending.json — and exited 0. Three independently wrong consequences: automation could not
tell a failed model from a good one; the queue pointed at a checkpoint that did not exist
(`resume` answered "No unfinished run found"); and — the structural one —
HumanReviewQueue.requires_signoff has ALWAYS counted a validation error as blocking, but
`passed` is false precisely when an error issue exists, so that branch could never fire from
the graph. The product documented a human gate it never opened. (§2.1) The exhausted budget
now routes to HUMAN_CHECKPOINT_NODE, so that branch is LIVE: the run pauses with the errors
in the queue and the human decides. It deliberately does NOT go through the source mapper
first, unlike the passing path — mapping concepts of a model that may be discarded spends
LLM calls on output that may never be used (pinned by a test asserting source_mapper is
absent from the failed path's decisions). (§2.2) New exit code 3 = "completed, but the model
does not validate", keyed on validation_report.passed at every point a CLI invocation ends —
1 stays pipeline failure, 2 stays Click usage, and a pause for an unassigned contract owner
stays 0. It fires whether the run is still paused OR a human accepted at the checkpoint:
accepting does not make the artifacts valid. One plain line says what the artifacts are for
(diagnosis, not deployment). (§2.3) adr_author renders a prominent caveat directly under the
header — not buried in Consequences — naming the surviving error codes and constructs
(matched on severity, never message text) and stating the model was accepted despite them;
an ADR documenting a known-broken model silently would be worse than no ADR. It keys on the
error ISSUES rather than on `passed` alone, because ValidationReport.passed defaults to False
and a state that never reached the validator would otherwise get a caveat announcing "0
surviving errors". Also fixed, a wrongness this WP made reachable: the pause message told the
human to "assign the contract owner(s)" even when nothing was waiting for an owner — it now
names the two decisions that actually apply (--accept / --discard) when no contract_owner item
is in the queue, and is byte-identical otherwise. Live evidence, both paths: `run` → exit 3
with the pause and the explanation; `resume --accept` → "run finalized" + exit 3, ADR carrying
"E_SAT_DUP_ATTR (sat_customer_details)". Docs: exit-code table (operations 06 §6.6, incl. why
3 is the one to script against), the "three failed attempts" line that was NOT true of the
exit code, two troubleshooting rows, and a dated refinement note in ADR-0006 (the architecture
overview needed none — it already described this behaviour, which is the point).
test_persistent_failure_stops_at_retry_cap was updated DELIBERATELY (it encoded the old
contract) and still pins the bound: the modeler runs exactly MAX_MODELING_ATTEMPTS times.
557 tests green (+6: checkpoint reached with requires_signoff and an interrupt, accept →
finalise with the caveat, CLI exit 3 + resumable pending + no ADR yet, accept → exit 3 with
the caveat on disk, --discard, mapper absent from the failed path), ruff clean, mypy strict
clean (37 files).

WP27 hygiene landed (as of 2026-07-29,
docs/architecture/backlog-2026-07/wp27-ci-retry-hygiene-spec.md, review finding 5), three
small things. (§2.1) CI type-checked LESS than the DoD: `.github/workflows/ci.yml` ran
`uv run mypy src`, and an explicit path OVERRIDES pyproject's
`files = ["src/vault_agent", "eval"]` — so eval/ (2,000+ lines carrying the quality gates
everything else leans on) was strict-checked locally and not in CI. The workflow now runs
the bare `uv run mypy`, with a comment stating why the invocation must stay bare.
METHOD NOTE worth keeping: the first verification of this used
`uv venv` + `uv pip install -e ".[dev]"` and reported a FAILURE
(`eval/run.py:190: Unused "type: ignore"`), which would have been a false alarm —
`uv pip install` ignores uv.lock and resolves fresh versions, while CI uses `uv sync`.
Re-run CI-faithfully via `UV_PROJECT_ENVIRONMENT=<tmp> uv sync --extra dev`, the whole CI
job is green (mypy 37 files, 567 tests, ruff) with no extra dependency needed. It does show
the ignore is version-sensitive: an unlocked resolution flags it, so a langgraph bump may
require touching that pragma. (§2.2) The retry policy honoured no server advice: 408/429/5xx
were retried at a fixed 2/4/8 s, so a key answering `Retry-After: 30` failed the whole call
after ~14 s of waiting guaranteed to be too short, and parallel runs (eval --repeat, ablation
arms) retried in lockstep and re-collided. ForcedToolCaller now derives each delay from the
failure that caused THAT retry: `retry-after-ms` then `retry-after` (read defensively —
verified against the installed anthropic 0.107.0, where APIStatusError.response is an
httpx.Response; a non-numeric HTTP-date value falls through rather than being guessed at),
else the exponential base with EQUAL jitter (d/2 + rng()*d/2, chosen over full jitter because
the failure mode is a rate-limit collision: decorrelate, but never retry almost immediately).
Every wait is capped at _MAX_RETRY_DELAY_SECONDS=60 so a hostile header cannot hang a run,
and logged at INFO with its length and which policy applied. rng is injectable next to the
existing sleep seam; the test helper injects rng()==1.0, which collapses equal jitter to
exactly the base delay, so the pre-WP27 2/4/8 assertions keep pinning the same ladder
unchanged. Status set, _MAX_RETRIES, non-retryable propagation and trace events are
untouched. (§2.3) cli._read_pending did a bare json.loads and `resume` called it outside any
try, so a truncated or hand-edited pending.json — a file WP17 now points users at — surfaced
as a raw JSONDecodeError traceback. It raises an attributable ValueError naming file and
problem (house loader style), also rejecting a document without a thread_id; `resume` catches
it and exits 1 with the message. The instructions deliberately do NOT offer `--discard`: it
reads the same pointer and would fail identically — deleting the file by hand is the only way
through, and the orphaned thread is pruned by the next run. The already-guarded callers
(_report_crashed, _prune_orphan_threads) keep swallowing it, pinned by a test. 567 tests green
(+10: Retry-After honoured, retry-after-ms, absurd header capped, unparseable header falls
back, jitter halves at rng()==0 and never exceeds base, connection error without a response,
CI workflow drift guard, corrupt pointer message, missing thread_id, guarded callers still
swallow), ruff clean, mypy strict clean (37 files).

WP22 streaming landed (as of 2026-07-29, ADR-0010 Accepted,
docs/architecture/backlog-2026-07/wp22-streaming-spec.md), lifting the transport ceiling
that blocked scale_100/300. ForcedToolCaller.call moved from the non-streaming create to
the SDK's streaming helper (`async with client.messages.stream(...) as stream:` +
`await stream.get_final_message()`) as ONE code path — no streaming/non-streaming
conditional, because a second path is a second thing that can rot. Everything else is
byte-identical: same forced single tool + tool_choice, same cache-controlled system block
(WP3 caching and the WP16 fixture pins untouched), same retry matrix, same truncation
detection, same usage capture and WP15 trace events. Verified against the INSTALLED SDK
rather than assumed (the WP8 t_link lesson): `get_final_message()` returns the accumulated
Message with cache_read_input_tokens folded in by the accumulator, and both failure
surfaces stay inside the existing try — the initial request is awaited by the manager's
`__aenter__` (so an APIStatusError there still carries status_code for the retry matrix),
a mid-stream failure surfaces from `get_final_message()`. Two numbers corrected while
implementing: the non-streaming limit was never "roughly 16k" — the SDK raises when
3600*max_tokens/128_000 > 600, i.e. above 21,333 — and `claude-opus-4-8` allows 128,000
output tokens (confirmed against the live Models API, not memory). The modeler budget went
16384 -> 32768, deliberately NOT to the model maximum: it clears the ~26k 300-table
extrapolation with ~26% headroom while bounding a runaway generation's cost, and the
constant is now PINNED by a test (it had been unpinned) that also asserts the rationale
cites ADR-0010, so the next person raising it finds the exit condition — staged modelling /
domain partitioning — instead of just bumping the number again. Test seam: the stub client
offers ONLY `messages.stream` (a plain method returning an async CM), which is what proves
acceptance #1's single path — `grep messages.create src/vault_agent` finds nothing. Every
pre-existing test_llm.py behaviour is re-pinned against streaming by construction.
Acceptance #3 (live smoke) is CLOSED, not deferred: a real emit_dv_model call on
claude-opus-4-8 streamed at max_tokens=32768 and landed in the trace with
stop_reason=tool_use, 629 in / 759 out tokens and the full payload (2 hubs, 1 link, 2
satellites incl. an effectivity sat). 573 tests green (+6: single-path proof, request-kwargs
identity, payload/usage/trace from the final message, retryable and non-retryable errors
while opening the stream, budget pin), ruff clean, mypy strict clean (37 files). NB the
scale_100/300 measurements this unblocks are still OPEN — the transport no longer caps them,
which is not the same as having run them.

## References
- In-repo methodology notes: docs/methodology/ (DV2.0 rules cheatsheet, IREB mapping, DSAF
  mapping, data-contracts approach)
