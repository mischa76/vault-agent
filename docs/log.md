# Project log

Append-only, chronological. One entry per closed work package, live measurement, spike or
correction — newest at the bottom. Every entry starts with `## [YYYY-MM-DD]`, so the timeline is
greppable:

```
grep "^## \[" docs/log.md | tail -5
```

**Entries are never rewritten.** A later finding that changes how an earlier entry should be read
gets its own entry that says so; the earlier text stays as it was written. This is the same rule
the ADRs and WP specs follow (WP28: *"resolved, history not rewritten"*).

Entries dated 2026-06-11 to 2026-07-30 were moved here **verbatim** from the `## Current
milestone` section of `CLAUDE.md` on 2026-07-31, in their original order; only the `## [date]`
headings were added. Nothing was summarised, condensed or corrected in the move — a mechanical
check (`scripts/check_log_completeness.py`) asserts that every paragraph of the pre-retrofit
`CLAUDE.md` appears here byte-for-byte. Rationale for the move and the structure that replaced
it: `docs/methodology/llm-wiki-mapping.md`.

Statements below were true when written and are **not maintained**. Where an entry states a
count, a version or a threshold, the code owns the current value — see the invariants in
`CLAUDE.md`.

---

## [2026-06-11] Core pipeline runs end-to-end — 6 agents, LangGraph, CLI

Core pipeline runs end-to-end (as of 2026-06-11). Built: 6 agents
(requirements_parser, business_key_identifier, dv2_modeler, code_generator, validator,
adr_author) wired into a LangGraph state machine (graph.py) with a self-correcting
validation loop (validation fails → re-model, bounded by MAX_MODELING_ATTEMPTS) and an
ADR branch on success. Code generator emits AutomateDV dbt models for hubs, links,
standard/multi-active/effectivity satellites, and non-historized links, plus metadata.
CLI (`vault-agent run <doc> --out <dir>`) writes models, metadata, and the ADR to disk.
Two demo datasets (bank, health insurance) run through the full pipeline. Tests green
without an API key (LLM calls are injectable/stubbed); ruff + mypy strict clean.

## [2026-06-13] DV2.0 modeling rules encoded — [ENFORCE]/[GUIDE] split

DV2.0 modeling rules are now encoded (as of 2026-06-13) per the Linstedt/Olschimke
canon (dv2-modeling-rules-spec.md), split into [ENFORCE] rules (validator gates) and
[GUIDE] rules (modeler prompt). The validator has independent gates with E_/W_ codes (28 as of
2026-07-08 / WP7; may grow — count the codes in validator.py, don't trust prose)
enforcing driving keys, grain, attribute overlap, wide-satellite splits, and BK
collision; rules/dv2_rules.py holds the UoW/driving-key/splitting/collision guidance,
SATELLITE_SPLIT_AXES, and SAT_WIDE_ATTRIBUTE_THRESHOLD. State carries Link.driving_key
(required for effectivity), Link.unit_of_work, and Satellite.split_rationale for the ADR
trail, which the adr_author surfaces when present.

## [2026-06-13] Architecture-review remediation

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

## [2026-06-14] data_contract agent (ADR-0005)

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

## [2026-06-14] Orchestrator and the deterministic review queue (ADR-0006)

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

## [2026-06-15] Live HITL interrupt/resume (ADR-0006, second half)

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

## [2026-06-15] Status note — no agents remain as stubs

No agents remain as stubs; the HITL loop is closed. Planned: transactional-link payload
modeling improvements, LangSmith evals, and (when a UI lands) an interactive resume prompt.

## [2026-06-23] Generated models run on a real warehouse — bank Postgres PoC

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

## [2026-06-23] Incremental eff_sat fixed — APPLIED_DTS

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

## [2026-06-24] Source-schema input producer — --source-schema

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

## [2026-06-25] Reality-test remediation batch 1

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

## [2026-07-06] Hardening P1+P2 — typed flags, shared ForcedToolCaller

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

## [2026-07-06] P3 staging generator — the output becomes a runnable dbt project

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

## [2026-07-07] WP4 — typed ValidationIssue

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

## [2026-07-07] WP2 — ADR author remediated

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

## [2026-07-08] WP1 — four new validator gates

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

## [2026-07-08] WP3 — LLM cost and robustness

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

## [2026-07-08] WP6 — the eval harness

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

## [2026-07-08] WP7 — staging refinements

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

## [2026-07-08] WP5 — hygiene batch

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

## [2026-07-08] WP8 — role-qualified link hub references (ADR-0009)

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

## [2026-07-13] Business↔source mapping design spike — Phase 2 resolved (ADR-0008)

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

## [2026-07-13] WP9 — business↔source mapping (ADR-0008)

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

## [2026-07-13] WP9.1 — mapping remediation

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

## [2026-07-13] WP9.2 — mapping-scorer universe fix

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

## [2026-07-14] WP9 §10.7 — opacity probe closed

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

## [2026-07-14] WP10 — multi-source hub

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

## [2026-07-14] WP9 §10.8 closed — and promoted to demo/mapping_postgres

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

## [2026-07-15] data_contract truncation bug fixed — bounded enrichment units

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

## [2026-07-15] messy_insurance completes end-to-end (verification run)

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

## [2026-07-16] Modeler CDK-dedup fix

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

## [2026-07-18] WP11 — static HTML run report

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

## [2026-07-18] WP12 — interactive checkpoint prompt

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

## [2026-07-18] WP13 — scale-hardness tooling (keyless half)

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

## [2026-07-19] WP14 — column-based mapping coverage

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

## [2026-07-20] WP14.1 — crash-safe eval-run persistence

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

## [2026-07-22] WP15 — LLM trace capture

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

## [2026-07-22] WP16 — steering registry, backstop telemetry, release re-test

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

## [2026-07-27] Live verification batch — three measurement items closed

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

## [2026-07-28] Two findings from that batch — F1 parser cap, F2 link-name scorer

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

## [2026-07-28] Recorded, not fixed — _f1 treats an empty golden inconsistently

Also recorded, NOT fixed: `_f1` treats an empty golden inconsistently — with no golden constructs
declared, construct_f1 returns 0.0 (matched==0) while driving_key_accuracy returns 1.0 ("no
golden driving keys declared"). Both mean "nothing to check", with opposite answers; this is why
the scale_30 result JSON reads construct_f1 0.000 (`hubs: 0/0 golden matched, 17 generated`)
although the synthetic cases carry a golden MAPPING and no golden MODEL at all. Not a quality
signal — do not read it as one. 437 tests green (+4 in tests/test_eval_scorers.py: reversed name
component order matches, self-reference grain stays distinguishable, ambiguous grain resolved by
name, unresolvable tie stays a miss), ruff clean, mypy strict clean (37 files).

## [2026-07-28] Requirements-parser breakpoint fixed — adaptive segmentation

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

## [2026-07-28] Output-budget hardening — status and the failure class

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

## [2026-07-28] Output-budget hardening — the two output shapes

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

## [2026-07-28] Output-budget hardening — measured numbers and the method note

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

## [2026-07-28] Eval — a scorer with nothing to check is vacuous, not failing

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

## [2026-07-28] WP18 — eval gate integrity

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

## [2026-07-28] WP19 — contract truncation split

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

## [2026-07-28] WP20 — name gates

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

## [2026-07-28] WP17 — CLI crash recovery

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

## [2026-07-28] WP21 — robustness and hygiene batch

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

## [2026-07-29] WP24 — multi-source composition correctness

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

## [2026-07-29] WP26 — ADR completeness

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

## [2026-07-29] WP25 — a failed run becomes a first-class outcome

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

## [2026-07-29] WP27 — CI, retry and pointer hygiene

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

## [2026-07-29] WP22 — streaming (ADR-0010)

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

## [2026-07-29] WP23 — brownfield mode, Phase 1

WP23 brownfield mode, Phase 1 CORE landed (as of 2026-07-29, charter
docs/architecture/backlog-2026-07/incremental-extension-charter.md Accepted, spec
wp23-incremental-extension-spec.md). PARTIAL — read the open list at the end of this
paragraph before assuming a piece exists. `run --existing <dir|file>` extends a previously
generated vault instead of modelling into an empty target: the everyday DV2.0 scenario, and
per the charter the methodically correct answer to the scale axis (nobody models 300 tables
in one pass; they model domain by domain into a growing vault). The inertness guard was
written and committed FIRST (tests/test_greenfield_inertness.py): the whole write_outputs
tree of a bank run is pinned as a per-file sha256 manifest, so without the flag every
artifact stays byte-identical and a deliberate addition has to be named in _EXPECTED_NEW;
the WP10, staging-regression and both demo guardrails passed untouched throughout.
(§2.1) write_outputs now also emits metadata/dv_model.yml — the LOGICAL model. This
CORRECTS the charter's §3.1 guess that automatedv.yml could be round-tripped: that file is
the RENDERED macro view and carries no descriptions, requirement_ids, sat_type, driving
keys, source_table or Hub.sources, so reconstructing a DVModel from it would have had to
invent exactly the fields it lost. New loader src/vault_agent/existing_model.py in the
source_schema house style; a pre-WP23 output directory is an attributable error telling the
user to regenerate once, never a guess. (§2.2) state.existing_model (checkpointer-safe, so
resume needs no flag), --existing/-e, ExecutionPlan.extending, run-summary mode line.
(§2.4) agents/model_merger.py: new constructs append in delta order; an existing hub matched
BY NAME gains only its new source feeds (normalised dedup per E_HUB_DUP_FEED). A changed
business key or a re-stated link/satellite is a migration, so it is flagged
FlagKind.EXTENSION_CONFLICT and DROPPED rather than applied — the merged model therefore
still satisfies the gates and the human sees one story. The existing model is never mutated.
One subtlety worth knowing: when a single-source hub gains a feed, its original feed is
implicit (Hub.sources empty), so the merger materialises it as (source_entity, business_key)
— otherwise the merge would silently drop the legacy feed the moment sources became
non-empty. (§2.5) Five additive gates over (existing, merged), inert when greenfield:
E_EXISTING_REMOVED / _BK_CHANGED / _GRAIN_CHANGED / _SAT_RESHAPED plus the advisory
W_EXISTING_EXTENDED inventory (the review queue's extension category — validation warnings
already flow there, so charter Q5 needed no new ReviewKind). Per charter Q3, satellite
attribute GROWTH counts as a reshape too: a new attribute on a satellite with history is a
backfill, and new attributes belong in a NEW satellite on the same parent. (§2.6)
Grandfathering, the trickiest part: a feed the vault already had keeps its legacy
stg_<entity> name instead of gaining a WP10 source suffix, and an existing satellite is
NEVER split per source — either would rename a materialised dbt model holding history, i.e.
perform the destructive migration this track exists to refuse. Derived from the existing
model (no new state field), so greenfield naming stays symmetric. (§2.3) The modeler gains
an extension prompt section: a compact IMMUTABLE inventory plus delta-only instructions,
returning '' when greenfield so the WP16 steering fixture and prompt caching are untouched.
604 tests green (+31 across loader round-trip, merger, the five gates, grandfathering and
the prompt section), ruff clean, mypy strict clean (39 files).
(§2.7) The extension diff is a first-class artifact: extension-diff.md plus an Extension
section in the HTML report, both rendering the SAME state.artifacts.extension_diff so they
can never disagree. Three sections — unchanged / extended / new — and the load-bearing part,
FILE-CHANGE ATTRIBUTION: which generated files a pre-existing construct's SQL actually
changed in, computed by regenerating the existing model alone through the real generator and
diffing the rendered artifacts (no heuristics; the same generator means any difference is a
real one). That is what makes charter §3.2's "unchanged SQL means unchanged tables" a promise
a reviewer can CHECK rather than take on faith — a grandfathered hub's SQL legitimately
changes when it starts unioning a second staging model, and the diff names that file.
Attribution failures are logged, never fatal: the diff is a reporting aid and must not cost
a user their artifacts. (§2.8) The delta-ADR documents only what this run decided — existing
constructs are not re-listed — plus an "Extends" section naming the source vault, its
construct counts and the diff artifact. WP26's module-level construct renderers were built
for exactly this and needed no forking, as intended.
Two bugs found and fixed while building the diff, both worth recording because they are the
same class — an implicit feed counted as if it were explicit. (1) legacy_feeds originally
grandfathered EVERY feed of a multi-source hub; for a hub that was already multi-source in
the existing vault that is wrong twice over — it would rename models generated with WP10
suffixed names, and every one of them would collapse onto the same unsuffixed name. Only the
implicit feed of a hub that was SINGLE-source can own stg_<entity>, which is now what the
helper returns (pinned by a three-feed no-collision test). (2) The diff's "new feeds" count
used positional slicing and so reported the materialised legacy feed as an addition; it now
asks the same legacy_feeds helper, so a reviewer is never told a feed appeared that has been
there all along.
613 tests green (+9 over the core commit: diff classification, file attribution, the
markdown artifact, the delta-ADR and its greenfield absence, the report section incl. hostile-
name escaping, and the multi-source grandfathering regression), ruff clean, mypy strict clean
(40 files). The two write_outputs count assertions were updated deliberately for the new
extension_diff key (the WP11 "report" precedent).
Acceptance #2 is MET: the bank_extension eval case is the first case that runs the pipeline
in extension mode. It ships the previously generated bank vault as existing_vault.yml (the
demo/bank_postgres model, the one verified on a real warehouse), a CRM source schema and CRM
extension requirements; the golden is the expected MERGED model — the five existing
constructs unchanged plus hub_campaign, link_campaign_customer, sat_campaign_details and,
per REQ-107, sat_customer_marketing as its OWN satellite on the existing hub rather than an
extension of sat_customer_details (which would be a backfill migration). Deliberately
conservative in the bank case's tradition: a responsible-manager hub and campaign-response
timing are defensible and are NOT golden, so a run that models them loses a little precision
instead of being required to guess the same way. EvalCase gains `existing` (resolved like the
other input paths) and eval/run.py feeds it as state.existing_model — the same input the
CLI's --existing provides. New scorer existing_construct_preservation: the share of the
extended vault's constructs that survived unchanged (not removed, not re-keyed, payload not
reshaped), gated at exactly 1.0 because this is the promise the mode makes — anything less
is a defect, not a quality signal. It deliberately re-measures what the E_EXISTING_* gates
enforce: an eval scorer checks the OUTCOME, since the mechanism could itself be wrong or be
bypassed by a future re-model mode. It is vacuous (1.0, VACUOUS_PREFIX) on greenfield, and
load_eval_case now REFUSES to let a greenfield case gate it — the WP18 rule applied to the
new scorer. Two pins updated deliberately: the shipped-case list and the bank case's exact
score set (which gains the vacuous 1.0). 620 tests green, ruff clean, mypy strict clean.
bank_extension was then RUN LIVE (2026-07-29, 3x3 runs) and earned its keep immediately by
finding two product defects and one design limitation — which is what an eval case is for.
Measured after the fixes: existing_construct_preservation 1.000 (the promise holds against a
real LLM), construct_f1 0.855, driving_key_accuracy 1.000, pipeline_health 1.000; the case's
gates pass and `eval.run` exits 0. (Defect 1) The merger flagged EXTENSION_CONFLICT on every
run for a delta that was CORRECT: Hub.source_entity is required, so a delta re-stating a hub
to add a feed must supply one, and the only sensible value it has is the NEW source's
(`crm_contact` vs the existing `customer`). Unlike the business key, source_entity is a
modelling input the collision gates read, not part of the hub's stored identity — nothing
hashed depends on it — so the check is gone and the existing value is simply kept. (Defect 2)
Source-schema grounding warned about every PRE-EXISTING attribute, because the declared
schema describes the source this increment integrates while the existing constructs were
grounded against a different one when they were created. One warning per old attribute is
pure noise and it is what pushed the case over its warning tolerance; grounding now skips
constructs present in existing_model (inert on greenfield). Warnings fell 16 -> 9.
(Limitation, NOT fixed — recorded in the case file and here) Validation still FAILS on this
case, so validation_gate reports 0.0; it is reported, not gated, and the expectation was
deliberately NOT flipped to hide it. Two stable causes across all 6 runs: (a)
E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB fires on the NATURAL brownfield shape — the modeler
correctly reads REQ-107 and emits a satellite fed by crm_contact on the now-multi-source
hub_customer. WP24 rejected that combination on the grounds that one relation cannot feed
two independent feeds, which is true when the satellite describes ALL of them and false
here, where it describes ONE. A steering rule was added through the WP16 registry and did
NOT prevent it (0/3 runs) — a clean datapoint that this needed a modelling decision rather
than more prompt text. That decision is now written: ADR-0011 (Proposed, 2026-07-29), which
narrows the gate instead of removing it — a satellite whose source_table NAMES one of the
hub's feeds binds to that feed and is generated once; everything else stays an error. It
rests on a measured fact worth keeping: with source_table left unset (what the steering
asks for) the WP10 split demands the CRM's columns from the CORE banking staging too, so
the alternative the gate steers to does not build either. bank_extension's validation_gate
is that ADR's acceptance signal. The prompt fixture and the steering ledger were
updated deliberately in the same commit (WP20 precedent), with the pre-WP16 block asserted
to still be a byte-identical prefix. (b) E_HUB_HK_COLLISION on hub_campaign/hub_employee:
the modeler gives both source_entity 'crm_campaign'; a genuine modelling smell the gate
correctly catches, and hub_employee is not golden. Method note: after the first live run,
the second and third diagnoses came from REPLAYING the stored trace through merge+validate
at zero API cost — the 2026-07-28 lesson applied.
Spec §3.8 and the docs are done: CLI tests cover --existing as a directory and as the file
itself (both reaching a real extension through the graph with the REAL code generator, so the
diff artifact is actually asserted rather than stubbed away), the greenfield mode line, the
attributable pre-WP23 error, and typer's exists=True usage error; operations 06 gains §6.7
(brownfield mode: the may/may-not table keyed to the E_EXISTING_* codes, why regenerating
everything is safe, grandfathering, the delta-ADR, and the known limitation), plus the
--existing row, the mode line, dv_model.yml and extension-diff.md in the output anatomy, and
three troubleshooting rows. Also implemented here: the counts key `model` that §2.1 asked for
and the core commit missed. 627 tests green, ruff clean, mypy strict clean (40 files).
WP23 acceptance #3 is MET (2026-07-29, PostgreSQL 16 + AutomateDV 0.11.4): the extension
output builds green ON TOP of a previously built vault. Method: the fixed bank model was
generated and built into an isolated schema (`dbt build --full-refresh`, PASS=12) — that is
the "existing vault"; its metadata/dv_model.yml then fed a deterministic CRM extension (no
LLM: hub_customer gains a crm_contact feed, plus hub_campaign, link_campaign_customer,
sat_campaign_details, and sat_customer_marketing BOUND to the crm_contact feed — the
ADR-0011/WP28 shape); the v2 project was built over the same schema **without
--full-refresh**: PASS=22 WARN=0 ERROR=0, and a second run changed nothing (idempotent).
Data-level additivity, which is what the charter asked for rather than SQL-level: 5 of the 6
pre-existing constructs are byte-identical by row count AND content hash
(hub_account, link_account_customer, sat_customer_details, sat_account_details,
sat_account_customer_eff). The single change is hub_customer, and it is purely additive —
all 3 original BANK.CORE rows still present with their original load timestamps, plus 1 row
for the CRM-only customer. The integration property holds at the data level: CH-1001 and
CH-1002 each have ONE hub row carrying BOTH a core satellite row and a CRM satellite row,
CH-1003 is core-only, CH-9001 CRM-only. New constructs populated (campaign 2, targeting 3,
campaign details 2, marketing 3). This also proves WP28 on a warehouse rather than
structurally: sat_customer_marketing is a satellite bound to one feed of a multi-source hub,
and it builds and loads.
The build found one more defect first — before the database was touched, which is the point
of probing: a GRANDFATHERED feed kept its staging model's NAME but not its BINDING. The
merger materialises a single-source hub's implicit feed as (source_entity, business_key),
and the multi-source branch bound every feed verbatim to its source_table, so `stg_customer`
silently stopped reading `raw_customer` and started reading `customer` — a relation that does
not exist (the build breaks) or does and is the wrong data. A legacy feed now gets NO binding
in that branch and keeps the one bind_sources derives, exactly as the single-source hub did.
Preserving the name without the binding is not preserving the model; pinned by a test that
compares the before/after `source_model` directly. 640 tests green, ruff clean, mypy strict
clean (40 files). WP23 Phase 1 is COMPLETE — every acceptance item met.

## [2026-07-29] Brownfield Phase 2 spike — entity resolution

The brownfield Phase 2 spike ran (2026-07-29,
docs/architecture/backlog-2026-07/spike-entity-resolution-charter.md ->
spike-entity-resolution-results.md), following the mapping spike's protocol: charter first,
throwaway prototypes under spike/ (deleted at the end), only docs and eval assets survive.
The charter set one thing apart from its template and it shaped everything: entity resolution
is NOT symmetric. A false merge — declaring a new source's concept to BE an existing hub when
it is not — pushes foreign business keys into a table holding live history, while a false
split costs a redundant hub someone deletes. So the primary metric is a zero-false-merge
requirement, never averaged with accuracy. Measured, 5 repeats per configuration on a golden
set carrying four trap classes (synonym hub / false friend / similar-name-new-hub /
same-as candidate, with two concepts sharing the "PARTNER" stem resolving in OPPOSITE
directions so a name-matcher cannot pass both): BOTH mechanisms produced zero false merges
across 25 runs; LLM-first scored 1.000 on all four metrics clean vs deterministic-first's
0.667 accuracy, at +13% input tokens, one call, Sonnet-tier. The decisive evidence is the
blinded probe — names masked to TBL_01/COL_01_02 and every comment stripped — where it
answers `unresolved` at confidence 0.35 exactly where it can no longer know while staying
right where structure alone decides, and its calibration margin RISES (0.054 -> 0.270 ->
0.383). It degrades honestly instead of guessing confidently, which was the disqualifying
test. Secondary finding worth acting on: the twice-deferred same-as concept is reliably
distinguishable (identified 5/5 clean AND when blinded), so it can become a model field.
Recommendation (for Mischa): build it LLM-first, grounding-gated, as a PRE-MODELING step with
its own ratification file rather than a modeler prompt section — once the modeler names a
construct, WP23's merge_models folds it by name and the decision is already made. Four
conditions are written into the memo, of which two matter most: the confidence CATEGORY must
be derived deterministically from the evidence (the model's self-reported category was wrong
on every exact-key case even where its answer was right), and the golden set must GROW before
a WP is scoped on it. The memo is deliberately explicit about what six concepts on one case
does not establish — including that the golden set and the prompt were written in the same
session by the same author, a real confound the blinded probe mitigates but does not remove.
Surviving assets: eval/datasets/brownfield_resolution/, eval/resolution.py, four scorers in
eval/scorers.py with 15 keyless tests, and the raw runs under eval/results/spike_resolution/.
655 tests green, ruff clean, mypy strict clean (41 files). Spike cost: ~$0.30.

## [2026-07-29] WP29 specced from the spike — with a fifth trap added

The spike's recommendation was accepted and specced as WP29
(docs/architecture/backlog-2026-07/wp29-entity-resolution-spec.md + kick-off), NOT yet built.
Two things about it are worth knowing before someone picks it up. (1) The golden set gained a
FIFTH trap after the spike ran — `undecidable`: a legacy migration register whose key has the
same format as the national customer ID, with no cross-reference table and nothing in the
schema that settles whether the populations overlap. The only correct answer is `unresolved`.
It exists because the memo criticised its own measurement for never offering the hardest
case, and it is now MEASURED (memo §6a, 2026-07-29): `unresolved` 5/5 clean, with evidence
naming the missing cross-reference explicitly — "no explicit cross-reference is provided …
merging risks injecting legacy keys into live history … a data lineage review or explicit key
mapping is required". WP29 acceptance #2 is met. Two findings from that measurement are worth
carrying: (a) the FIRST probe used a prompt into which I had written a sentence describing
trap 5 almost verbatim — teaching to the test, exactly the confound the memo warned about.
Re-measured without it: identical result. The confound was real and did not carry the result,
and the check is recorded because performing it is the point. (b) BLINDED, trap 5 flips to
`NEW` at confidence 0.88 — no false merge, but a confident wrong answer where the other
blinded concepts correctly fell to 0.35. The honest reading is that the blinded probe cannot
test this trap at all, because the trap's difficulty lives entirely in the comment that
blinding removes; the concept should be excluded there rather than read as a failure. What
survives as a genuine limit: the mechanism is honest where it can SEE that it lacks evidence,
and confident where the evidence of its own uncertainty is what got removed. WP29 must
therefore not lean on the confidence number alone — the derived category is what carries the
reviewer's attention. (2) Two spec
decisions come from measured failures rather than taste: the confidence CATEGORY is derived in
rules/ because the model self-reported `semantic` for every case including the exact-key ones
where it was right, and the resolver is a PRE-MODELING step with its own ratification file
because once the modeler names a construct, WP23's merge_models folds it by name and the
decision is already made.

## [2026-07-29] WP29 — deterministic core built

WP29's DETERMINISTIC CORE is built (2026-07-29) — the agent, graph wiring, ratification file
and CLI are NOT, and that split is deliberate rather than an accident of where the session
ended: the core is the part that is fully testable without an LLM, so it is worth landing on
its own. state.py gains ResolutionProposal / EntityResolution (with `is_merge`, the property
the zero-false-merge requirement is expressed in) plus the reserved answers NEW /
same_as_candidate / unresolved as RESOLUTION_CLASSES, and state.resolutions. rules/ gains
resolution_category(), which DERIVES the confidence tier — exact_key > key_overlap >
comment_grounded > semantic — from the schema and the evidence rather than trusting the
resolver's own claim. That helper exists because of a measurement, not a preference: the
spike's resolver reported `semantic` for every case including the exact-key ones where its
answer was right, so a self-reported category cannot carry a reviewer's attention. A test
pins exactly that contrast (claimed `semantic` vs derived `exact_key` on the same proposal).
660 tests green (+5), ruff clean, mypy strict clean (41 files). What remains for WP29:
agents/entity_resolver.py (one forced-tool pass, grounding-gated, inert without BOTH an
existing model and a declared schema), graph placement before dv2_modeler,
resolutions.review.yml + `resume --resolve`, the two review-queue flag kinds, and the live
acceptance runs of spec §4.

## [2026-07-29] WP28 — satellite feed binding (ADR-0011)

WP28 satellite feed binding landed (as of 2026-07-29, ADR-0011 Accepted,
docs/architecture/backlog-2026-07/wp28-satellite-feed-binding-spec.md), implementing the
decision WP24 §5 deferred and WP23's live run forced. A satellite whose `source_table` NAMES
one of its multi-source hub's feeds is now generated ONCE, bound to that feed's staging —
the DV2.0-canonical one-satellite-per-source shape the pipeline used to reject. The gate
narrowed rather than disappeared: `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` keeps its name and
now errors only when the named table is not a feed at all, because a finer-grain relation
UNDER one feed cannot say which feed it belongs to and inventing that binding is not
something this project does; the message lists the available feeds. New
`rules.satellite_feed()` answers "which feed?" beside the existing predicate, so all three
call sites still ask one place. Two things the implementation had to get right and did:
the type restriction (only standard satellites split) belongs to the SPLIT, not to binding —
a multi-active satellite bound to one feed is an ordinary satellite, so the check moved
below the binding branch; and a grandfathered LEGACY feed matches by name like any other, so
an extension satellite naming it reads the unsuffixed `stg_<entity>` (pinned, not assumed).
The staging fix is what inverts the ADR's probe: a bound satellite's columns and hashdiff go
to THAT feed's spec only, so the core banking staging stops being asked for the CRM's
columns. Measured before/after on the same model — before: both stagings demand
MARKETING_SEGMENT and two satellites are emitted; after: only `stg_customer_crm_contact`
does, and one satellite is. WP16 bookkeeping: the `no_source_table_on_multi_source_hub`
steering rule added the same day is DELETED — it argued against the shape the ADR blessed —
with the prompt fixture regenerated and the ledger row moved to a deleted state carrying its
evidence (0/3 effective). It is the ledger's first rule retired on measurement rather than
taste, which is what LOOPS rule VIII asked for. The WP24 composition matrix's cell 6 split
into 6 (feed-naming, generated) and 6b (non-feed, still flagged), and the one-hash-input-set
invariant holds over both. LIVE ACCEPTANCE (3 repeats, 2026-07-29): the primary signal is
met — all three runs emit the REQ-107 satellite with `source_table='crm_contact'`, the gate
fires 0/3, and each generates exactly one `sat_customer_marketing` bound to
`stg_customer_crm_contact`. Reported alongside per the ADR's sharpened signal:
`validation_gate` rose 0.000 -> 0.667 (it is confounded by `E_HUB_HK_COLLISION` on
hub_campaign/hub_employee, which the modeler produces on some runs and which was explicitly
out of scope), `existing_construct_preservation` stayed 1.000, `construct_f1` 0.855. Docs
updated in the same commit: gate catalogue (narrowed meaning + the dated note that WP24
originally rejected everything), WP24 spec §5 (resolved, history not rewritten), operations
§6.7 (the limitation paragraph became guidance) and the troubleshooting row. 639 tests green
(+9), ruff clean, mypy strict clean (40 files).

## [2026-07-29] WP30 — AdventureWorks instrument, keyless half

WP30's INSTRUMENT is built and its keyless half is complete (2026-07-29,
docs/architecture/backlog-2026-07/wp30-adventureworks-semantic-axis-spec.md, Approved) — the
live arm comparison (§2.6) is OPEN and is the only remaining acceptance work, so do not read
"the AdventureWorks cases exist" as "the domain-partitioning claim is tested". Eval-only; no
`src/vault_agent/` change is in scope. Why it exists: two recorded defects in our measuring
instrument. (a) The WP13 synthetic generator scales table COUNT and not semantics — at 100 and
300 tables the requirements carry exactly 87 distinct sentence templates and 200 of 296
entities are index variants of an archetype, so above the 30-table step `scale_100`/`scale_300`
measure tolerance for boilerplate rather than semantic breadth. (b) Every realistic case —
schema, requirements and golden — came from the same author as the prompts and the rules; this
pipeline had never once been measured against a schema somebody else designed. The instrument
is Microsoft's AdventureWorks OLTP sample (MIT — chosen over TPC-DI precisely because TPC's
EULA forbids derivative works and permits publishing only audited Benchmark Results, i.e. it
forbids the one thing we wanted it for; attribution ships as
eval/datasets/adventureworks/NOTICE). `eval/adventureworks/extract.py` parses the install
script into a checked-in `schema_extract.json`; `derive.py` transcribes it into per-subject-area
`source_schema.yml` + `golden_mapping.yml` (byte-deterministic, pinned by re-derivation).
Everything is TRANSCRIBED: the five OLTP schemas are the given partitioning and redrawing them
is forbidden by the spec, the 440 column comments are verbatim `sp_addextendedproperty` text
with the 25 undescribed columns left undescribed, and the golden holds ONLY Microsoft's own
single-column `AK_*` natural keys — never a column we judged to be one. So `mapping_coverage`
here answers one sharp question, *did the mapper find the real natural-key columns?*, and
deliberately nothing else. Two trap classes occur organically rather than being synthesised:
the `AK_*` natural keys, and the `rowguid` unique indexes beside them (the GUID-shadow trap
`messy_insurance` had to invent). Recorded correction worth keeping: §2.3 originally asserted
the script carries NO column descriptions, "verified" — it carries 440, and the error survived
two verifications that failed in the same direction (a WebFetch summary of a truncated
conversion, and a grep for the named-parameter form `@level2type=N'COLUMN'` when the script
uses positional arguments). The instrument as derived: 68 tables, 465 columns, 440 described,
24 natural keys, 26 false friends. Requirements were authored per subject area by a BLINDED
agent given ONLY that area's `source_schema.yml` (§2.4a) — the confound is reduced, not
removed, and each `dataset.yml` says how it was authored and that blinding was by instruction
rather than by sandbox. Cases: five greenfield subject areas, `adventureworks_full` (arm A, one
pass over all five — the five blinded documents concatenated UNEDITED, so both arms receive
identical input text) and `adventureworks_incremental` (arm B, the same five sequentially into
a growing vault). Gated on the structural scorers only — `mapping_coverage` >= 0.8,
`false_friend_hits` 1.0, `pipeline_health` 1.0, plus arm B's `existing_construct_preservation`
at exactly 1.0; `golden: {}` ships so the WP18 loader refuses to gate the name-keyed scorers,
and `validation_gate` is REPORTED not gated (an independent schema may legitimately trip gates
we have never exercised, and pre-committing to a pass would pressure the next person to weaken
a gate instead of recording a finding). The machinery §2.7 asked for is the real new code:
`EvalCase.chain` is a THIRD input mode (mutually exclusive with `input_document`/`generate`,
and forbidden alongside `source_schema`/`profiling`/`existing`), naming other cases in order;
`eval.run.run_chain_once` threads step N's `metadata/dv_model.yml` — written by
`write_step_vault` in the CLI's own bytes and location — into step N+1's `existing`, so a chain
exercises the genuine WP23 path rather than a shortcut that could diverge from what a user's
`--existing` sees. Two aggregation decisions are deliberate and both work against the
hypothesis rather than for it: chain review load is the SUM across steps, not the final step's
(a human reviews every increment), and preservation is the MINIMUM across extending steps,
never the mean. Arm B's step order is DERIVED from the extract's 90 foreign keys
(Person -> HumanResources -> Production -> Purchasing -> Sales) and was recorded in the spec
before any live run, so it cannot have been chosen after seeing a result; Person being the root
that both Sales and HumanResources reference is the natural WP29 entity-resolution case,
identified and documented (§4.5) but explicitly NOT measured here. The falsifying outcome is
written down first (§2.6): if arm A yields comparable review load and validation at lower total
cost, the charter's "domain by domain" claim is weakened and THAT is the finding — the losing
arm does not get quietly retired. Budget ceiling $40-60, per-case runs first. 680 tests green
(+13 tests/test_adventureworks.py: NOTICE, re-derivation determinism, every column traces to
the extract, comments verbatim incl. the undescribed ones, golden holds only Microsoft's AKs,
rowguid is a false friend and never a mapping, arm-B order follows the FKs, arm A is the union
of the areas and its document contains each blinded original, case/gate shape, chain
exclusivity, attributable missing-step error, step-vault round trip through the real loader,
preservation as min-not-mean with per-step attribution), ruff clean, mypy strict clean
(44 files).

## [2026-07-30] WP31 — E_SAT_ATTR_OVERLAP narrowed to one payload namespace (ADR-0012)

WP31 narrowed E_SAT_ATTR_OVERLAP to one payload namespace (as of 2026-07-30, ADR-0012 Accepted,
docs/architecture/backlog-2026-07/wp31-attribute-overlap-narrowing-spec.md), the first product
defect WP30's independent instrument found and the reason its two largest subject areas failed
validation. The gate errored on ANY repeated attribute label among the satellites of one parent.
On AdventureWorks that made a canonical shape unmodellable: Microsoft's per-entity history
tables (ProductCostHistory, ProductListPriceHistory) both hang off Product, so the correct model
is two satellites each declaring its own WP7 source_table — and their StartDate/EndDate columns
are different columns of different relations that merely share a generic name. Nothing collides
(WP7 §7.1 gives each satellite its own staging model), yet the gate errored, the modeler burned
all MAX_MODELING_ATTEMPTS, and the run ended at exit 3. The SAME run set also produced a TRUE
positive of the same code — Sales carried ModifiedDate in two satellites drawn from ONE relation,
which really is one column historised twice — and that contrast is the whole decision: this is a
narrowing, never a downgrade. E_SAT_ATTR_OVERLAP now errors only when the overlapping satellites
draw payload from the SAME source relation, and warns (W_SAT_ATTR_OVERLAP_CROSS_SOURCE, message
naming each satellite's relation) when the relations differ — reported rather than silent,
because a current-value satellite plus its history table looks exactly like this and IS a smell
worth a reviewer's eye (StandardCost did that here). rules.satellite_payload_relations() is the
single point that answers "which relation feeds this satellite?" (declared source_table; else
the hub's source_entity; else every feed of a WP10 multi-source hub, since the satellite splits
across them; else a link:<name> marker for a link parent, whose staging has no source table),
so validator and generators cannot drift — the WP24 lesson. Two satellites share a namespace iff
their relation sets INTERSECT, which is what makes the composition cases fall out with no
branches of their own: a WP10 split satellite spans every feed, so it still collides with a WP28
feed-bound one, and a source_table naming the parent's own relation is correctly the same
namespace written two ways (a real modeller did that in WP9 §10.8). An EMPTY set means "unknown"
(unresolvable parent) and is treated as sharing with everything — an unknown relation must never
LOWER a severity, which an empty set would otherwise do by intersecting nothing. Also added: the
WP16 steering rule attribute_one_satellite for the class that stays an error, deliberately
backstop=None — a gate refuses, it does not repair, and choosing WHICH satellite keeps a
duplicated column is a modelling decision, not a deterministic repair (the WP20 construct_naming
precedent); prompt fixture regenerated in the same commit with the pre-WP16 block verified to
remain a byte-identical prefix, ledger row added. Validator codes 34 -> 35 (23 E_/12 W_; the code
stays the source of truth). LIVE ACCEPTANCE (2026-07-30, 1 repeat each): production raises ZERO
E_SAT_ATTR_OVERLAP, its three hub_product overlaps are cross-source warnings, validation PASSES,
and it converged in ONE modeler attempt instead of three — so the fix also returns the re-model
budget it was wasting (75.8k -> 65.6k output tokens, 668 -> 589 s, $3.69 -> $3.02). Sales also
passes in one attempt and its ModifiedDate duplication did not recur; the steering rule is the
plausible cause but n=1 CANNOT separate a steering effect from sampling variance, so both the
spec and the ledger record one favourable datapoint rather than a demonstrated effect. Two side
effects of a validating model, both recorded in WP30 §7.3: review load collapsed (production
101 -> 45 items, sales 128 -> 50 — validation errors had been dominating those queues), and
mapping_coverage rose 0.000 -> 0.222/0.600 because WP25 deliberately SKIPS the source mapper on
the failed path, so the earlier zeros were zero PROPOSALS, not bad mapping — a correction to how
WP30's first findings read. 700 tests green (+20 in tests/test_agents/test_attribute_overlap.py:
the two measured shapes pinned from the traces so the measurement cannot regress, the namespace
rule across WP7/WP10/WP28/link/effectivity/unknown-parent cases, the helper parametrized over
ADR-0012's table, and the steering registry+ledger pins), ruff clean, mypy strict clean (44
files). Docs in the same commit: gate catalogue (count + narrowed meaning + the new warning row)
and both methodology cheatsheets.

## [2026-07-30] WP32 — a concept is (label, entity), not a label

Reconstructed on 2026-07-31 from commits `5af1fc7` and `baab04b`; this work landed after the
`CLAUDE.md` chronicle stopped being maintained, so it was never part of the moved text.

WP30's independent instrument found a wrong-DATA defect (the WP24 class, not a wrong message).
Three AdventureWorks reference hubs are each keyed `Name`: `_concepts` de-duplicated the mapper's
work-list on the label alone, so ONE concept was asked about, and `source_overrides` then applied
that single answer by label to every hub carrying it — `stg_address_type` hashed
`ADDRESS_TYPE_HK` from `PhoneNumberType`'s rows, silently, with the inferred-binding flag
CLEARED by the re-bind. `state.concept_key` / `split_concept_key` / `match_concept_refs` /
`resolve_concept_ref` are now the one definition of concept identity and of how a reference
resolves: the key exactly, else a label that is UNIQUE in its universe. Two rules the tests
forced: a qualified reference never label-matches a candidate carrying a different entity, and
"ambiguous" is a different answer from "unknown". The key is SENT to the model rather than
composed by it, so a label containing punctuation cannot produce an unparseable key. HITL is in
scope: `mappings.review.yml` emits a `key`, `--map` accepts either form, and a pre-WP32
checkpoint with bare labels still prunes. Amended in the spec rather than hidden: gaps/unresolved
now hold keys, which forced one eval change (`gap_detection` compares on the label half) after
§2.5 had claimed there would be none. Mutation-verified — 6 of the 16 new tests fail against the
pre-WP32 behaviour. 716 tests green, ruff clean, mypy strict clean (44 files).

Live results: `mapping_coverage` production 0.222 -> 1.000 (9/9), sales 0.600 -> 1.000 (5/5),
against the ~0.78 / ~1.000 predicted before the fix. Credit is split honestly — 7 of production's
9 are the `<TABLE>.NAME` collision this WP fixed, the other 2 were the Finding-3 key-choice
misses where the modeler simply chose differently this run. Acceptance §4.4 did NOT hold on
sales: `false_friend_hits` 1.000 -> 0.000, one proposal binding `rowguid -> SalesPerson.rowguid`.
Attribution from the traces: the MODELER put a replication GUID into `sat_quota_history`'s
payload in this run and in neither of the two before it, so the concept did not previously exist
— WP32 changed concept identity, not what the modeler emits, and no business-key concept was
bound to a GUID. Per WP30 §2.5 the gate is NOT edited because a run came out badly; both readings
are recorded and `false_friend_hits` now carries a standing caveat for the arm comparison, where
it can fail for a modeling reason.

## [2026-07-30] WP30 — per-step chain persistence, and the arm predictions written down first

Reconstructed on 2026-07-31 from commit `de237ef`. Two pre-run items, both keyless, before arm B
is paid for.

(1) A chain repeat costs ~$13-18 and WP14.1's crash-safety guarantee only held per REPEAT: a
five-step chain dying in step 5 discarded four completed, paid-for steps (§2.7's wording
described repeats, not steps). `run_chain_once` now takes an `on_step` callback and `eval.run`
persists each step the moment it completes, scored against that step's OWN golden, so partial
data is usable rather than a state dump. The callback is called defensively — bookkeeping must
never take the measurement down. Mutation-verified.

(2) Two predictions recorded BEFORE either arm ran, so they cannot become after-the-fact
explanations: the five subject areas are ONE source system, not five (proven by the shared key
space — 7 FKs from Sales into Person, the same `BusinessEntityID` being employee, customer and
store contact), so arm B measures incremental modelling of one landscape and NOT WP10 source
integration, and the writeup must not generalise; and hub reuse across steps will be imperfect
for a NAMING reason, because WP23's `merge_models` folds by name and step 5's modeler must
re-pick step 1's name from different text — predicted: at least one duplicate hub for a Person
concept, with `existing_construct_preservation` still 1.0, which belongs to the WP29 record
rather than to the partitioning verdict. 717 tests green, ruff clean, mypy strict clean.

## [2026-07-31] WP33 — an already-mapped concept is not re-mapped in the next increment (UNVERIFIED)

Reconstructed on 2026-07-31 from commit `699ec62`.

Found by the WP30 arm-B chain, and the same defect class WP23 fixed for the validator's
grounding — the source mapper never got the same treatment. Every step re-mapped the ENTIRE
accumulated vault against only that step's declared schema. A declared schema describes the
source this increment integrates; the pre-existing constructs were mapped against THEIR source
when they were created, so re-asking about them makes each one a fresh coverage "gap", every
step, for the rest of the vault's life. Measured across the five chain steps: gaps 4 -> 51 -> 80
-> 185 -> 208, where step 5's gaps are step 1's concepts (`Person::BusinessEntityID`,
`Address::AddressID`, …). That inflated arm B's review load to 983 items against arm A's 150 and
made the WP30 hypothesis untestable on those numbers. `_concepts()` now skips constructs present
in `state.existing_model`; greenfield has no existing model, so it is inert there, pinned by a
test.

**NOT verified.** The full suite has not completed since this change (the machine was loaded by
the live runs and the run was killed by a timeout). Targeted tests around the change are green —
source_mapper, concept identity, orchestrator, multi-source hub, eval run: 82 passed — and ruff
is clean. Run `uv run pytest` and `uv run mypy` before relying on it.

## [2026-07-31] Docs retrofit — CLAUDE.md becomes invariants, this log becomes the record

`CLAUDE.md` had reached 1,838 lines / 155,077 characters, of which ~47 chronological WP
paragraphs. It is loaded in full on every request, so the cost was paid continuously while the
content was needed rarely. The structural cause was that every WP appended a paragraph instead of
updating a state, which means any one-off cleanup regrows at the same rate.

Decided and applied: the chronicle moves here verbatim; `CLAUDE.md` keeps only invariants — the
sentences without which an agent silently does the wrong thing — in Trigger / Action / Evidence
form, under a 200-line budget with an admission rule (a promotion needs a concrete incident, and
at budget an eviction); `docs/index.md` becomes the catalogue that makes the rest reachable;
maintenance procedure lives in `.claude/skills/project-docs/`, subsystem conventions in
`.claude/rules/` where they load only when a matching file is read. `docs/architecture/` is
append-only: indexed and linked, never revised. Four rules that are craft knowledge rather than
project knowledge (verify against the installed library; write the byte-identity guard first;
audit existing traces before paying for another live run; branch on typed fields, never on
message text) were promoted to user scope, where every project inherits them.

The move is guarded rather than asserted: `tests/test_log_completeness.py` holds a sha256 per
pre-retrofit paragraph and fails if any of them stops appearing here byte-for-byte. It earned its
keep immediately — the first run failed and exposed a stray newline in the extraction, so the
guard is known to be able to fail. `.gitignore` was narrowed from `.claude/` to `.claude/*` with
`rules/` and `skills/` re-included: those are project instructions that must travel with the
repo, while local settings and worktrees stay ignored.

Rationale, the three deviations from the source pattern, and the verified Claude Code loading
semantics that shaped it: `docs/methodology/llm-wiki-mapping.md`. No `src/` or `eval/` code was
touched by this change. `CLAUDE.md` went from 1,838 lines / 155,077 characters to 150 lines /
9,896 — 6.4% of its former size, with the content moved rather than deleted.

## [2026-07-31] Contribution guidelines — the conventions become checkable

A clone now carries the conventions (the previous entry), but nothing asked a contributor to
follow them: there was no `CONTRIBUTING.md`, no PR template, and CI checks only pytest, ruff and
mypy. `CONTRIBUTING.md` states the definition of done — including why `mypy` must be invoked
bare, since an explicit path overrides the configured file list and silently skips `eval/` — the
keyless-suite rule, the knowledge-routing table, the append-only rule for dated records, and the
conventions that exist because something went wrong once (rules in `rules/` not in prompts, gate
versus backstop, branch on typed fields, verify against the installed library, guard before
change).

The section that carries the most weight is the vocabulary for verification:
**verified-live / keyless-only / not-measured**, with live evidence named (dbt PASS counts, the
trace file, eval scores). `.github/PULL_REQUEST_TEMPLATE.md` asks for exactly that as a checkbox
with an evidence field, alongside the write-down checklist and "anything a reviewer should push
back on". Its header tells contributors to answer "no" rather than delete a section.

Deliberately NOT added: a CI job requiring a `docs/log.md` change whenever `src/` changes. Such a
check can verify presence but not quality, and a gate that can only see presence produces empty
entries written to satisfy it.

## [2026-07-31] WP33's definition of done, completed

WP33 (`699ec62`) shipped with its own commit message saying the full suite had never completed
since the change — the machine was loaded by live runs and the run was killed by a timeout, so
only targeted tests (82) and ruff had been seen. It was the one place where this project's own
rule (tests, ruff and mypy green per commit) was knowingly broken, and it stood as the first
entry under "Open items" in `CLAUDE.md`.

Run now, on an idle machine: `uv run pytest` — **721 passed, 1 skipped in 22.6 s**; `uv run mypy`
— **no issues in 44 source files**; `uv run ruff check .` — clean. The single skip is deliberate
(`tests/test_greenfield_inertness.py`'s regeneration helper, run on purpose). Nothing needed
fixing; the earlier timeout was machine load, not the suite, which is worth knowing because it
was reasonable at the time to suspect the change.

What this does **not** establish, so that the WP30 entry keeps its meaning: WP33's effect on arm
B is unmeasured. Both AdventureWorks arms were run once, before this change, and the review-load
numbers that made the domain-partitioning hypothesis untestable (983 versus 150 items) have not
been re-taken. The open item is the arm comparison, not the code.

## [2026-07-31] First lint pass over the corpus — five gates were undocumented

The first run of the lint pass defined in `.claude/skills/project-docs/SKILL.md`, over the
maintained pages only (`docs/operations/`, `docs/methodology/`, the index, `README.md`,
`CLAUDE.md`, `CONTRIBUTING.md`, `.claude/rules/`). Dated records were read, never edited.

**The finding that mattered — the gate catalogue was incomplete, not just stale.**
`docs/operations/08-validation-gates.md` documented 35 codes; `validator.py` has 40. The five
missing ones are WP23's brownfield extension gates — `E_EXISTING_REMOVED`,
`E_EXISTING_BK_CHANGED`, `E_EXISTING_GRAIN_CHANGED`, `E_EXISTING_SAT_RESHAPED` and
`W_EXISTING_EXTENDED` — which were never added to the catalogue when brownfield mode landed. The
page's own arithmetic was self-consistent (23 + 12 = 35), which is exactly why nobody noticed: a
wrong total agreeing with an incomplete table looks correct. A new "Extension mode" section now
documents all five, written from the gate conditions rather than from memory — worth stating,
because `E_EXISTING_BK_CHANGED` does compare `source_entity` as well as the business key, and the
WP23 live-run fix that dropped a `source_entity` comparison touched the *merger*, not this gate.
Describing it from recall would have documented behaviour the code does not have.

Two more of the same class, both fixed by removing the number rather than correcting it:
`operations/03`'s pipeline diagram said "32 E_/W_ gates", and `README.md` advertised
"~430 tests" against an actual 721. The catalogue header no longer states a total at all and
carries the `rg` one-liner that produces the current set instead. Also mechanical:
`architecture/0-vision.md` and `3-diagrams.md` were missing from the index; every index link
resolves, and the only remaining unlisted files are the 33 kick-offs, which the index covers by
the naming convention on purpose.

Checked and clean: the steering ledger mentions all 17 registered rule ids; no contradictions
between maintained pages; `AUTOMATE_DV_VERSION` in `operations/05` states its value beside a
pointer to the constant, which is the acceptable form for a configuration reference.
`CLAUDE.md` is at 148 of its 200 lines. One self-audit finding, reported and not acted on: the
"Definition of done" invariant is a checklist rather than trigger/action/evidence, so by the
skill's own rule it is an eviction candidate — it is kept because it is the one entry a
contributor needs before every commit.

Not attempted here: the dated records under `docs/architecture/` contain historical gate counts
(30, 32, 33, 34, 35) that were correct when written and are wrong now. Append-only means they
stay. Anyone reading them should take the count from the code, which is what the invariant says.

## [2026-07-31] The append-only rule becomes enforced instead of requested

`CLAUDE.md` and `.claude/rules/records.md` both say never to edit a dated record, and both are
*context, not enforced configuration* — the documentation is explicit that there is no guarantee
of compliance. Of every convention in this knowledge base, append-only is the one that can be
enforced mechanically for an agent, so it now is: a `PreToolUse` hook
(`.claude/hooks/append_only_records.py`, registered in `.claude/settings.json`) denies
`Edit`/`Write`/`NotebookEdit` on a file that **already exists** under `docs/architecture/`, with
a denial message that names the alternative rather than only refusing.

Four deliberate non-blocks, each one load-bearing: **creating** a file there is untouched, since
a new ADR or spec is precisely how a decision gets recorded; `docs/log.md` stays appendable,
because appending happens through `Edit` and its guard is a test; a human with an editor is
unaffected, since this constrains agents, not people; and `Bash` is not policed — a determined
`sed -i` still gets through, which would cost shell parsing to close and buys little against an
actor who is not trying to cheat. The escape hatch for a legitimate status move (Proposed →
Accepted) is `VAULT_AGENT_ALLOW_RECORD_EDIT=1`, deliberately awkward.

**It fails open.** Malformed input, a missing field or any internal error exits 0 and lets the
normal permission flow decide — the same rule the trace and usage recorders follow: bookkeeping
must never be why work cannot proceed. Pinned by tests, together with the four decisions.

Verification, stated at the level it actually holds: the script's decisions are covered by seven
subprocess tests against the real stdin contract; the wiring was exercised by running the exact
command string from `settings.json` with `${CLAUDE_PROJECT_DIR}` set, which returned the deny
payload; and the matcher was checked to hit `Edit`/`Write` and miss `Read`. What is **not** yet
observed is Claude Code loading the hook at session start — a live probe in this session
(attempting an edit on ADR-0001 with a string that cannot match, so nothing could be written
either way) was answered by the Edit tool rather than the hook, because settings are read at
startup. First edit attempt on a record in the next session is the remaining evidence.

## [2026-07-31] Lint follow-up — the first pass compared the wrong pair of things

Opening the WP branch's pull request surfaced a contradiction the lint pass earlier today should
have caught: `CLAUDE.md`'s "Open items" claimed *"`scale_100` has never completed end to end"*
and *"the source-mapper segmentation is keyless-tested only — it has never run against the real
API"*. Both halves are false, and `scale-test-findings.md` already said so. `scale_100` completes
and validates since the enrichment-concurrency fix (candidate #4: 53.4 min incomplete → 13.6 min
complete), and the 100-table run records `emit_mapping` hitting 100% of cap with *"1 → split,
recovered"*, observed live — the segmentation the claim called untested is the segmentation that
run exercised.

The line was inherited verbatim from the pre-retrofit `CLAUDE.md`, where it was written on
2026-07-28 and was true then. Moving a stale claim into a shorter file does not refresh it.

Replaced with what the findings document itself concludes, which is a narrower and more useful
statement: **scale is verified at ~30 tables of real semantic variety and unverified above it** —
not because the pipeline breaks, but because the synthetic landscape does not scale *information*
with table count (candidate #5), so the upper cases measure width and repetition tolerance.
`scale_300` remains unrun, and `emit_dv_model` is the one agent that cannot split.

**Why the pass missed it, recorded because the checklist is now sharper for it.** The lint ran
maintained pages against *each other* and against the code — gate counts, version pins, test
totals — and never against the **record**. A claim in "Open items" is exactly the kind that a
later findings entry overtakes silently: nothing about it looks stale, no number is wrong, it
simply stopped being true. The skill's contradiction check now says to compare maintained pages
against the record and names "Open items" as the likeliest place.

## [2026-07-31] WP29 — entity resolution against an existing vault (keyless half)

Brownfield mode could extend a vault only because a *human* answered the one question it
cannot: "the new source calls this PARTNER — is that the existing `hub_customer`, or a new
hub?" The Phase 2 spike measured that the model can propose that answer safely (zero false
merges across 25 runs; blinded, it falls to `unresolved` at low confidence rather than
guessing). This builds the assist under the four conditions the spike set. The **live
acceptance runs of §4 are NOT done** — what landed is the mechanism and its keyless tests.

`agents/entity_resolver.py` runs BEFORE `dv2_modeler` (§2.1, binding: once the modeler names a
construct, WP23's `merge_models` folds it by name and the decision is already made) and is
inert unless BOTH an existing model and a declared schema are present — greenfield and
ungrounded runs make no call and change no state, which is the first thing the tests pin.
Concepts come from the identified business keys, de-duplicated on (label, entity) for the same
reason WP32 gave: two entities can carry the same key label, and one answer must not serve
both.

Three properties carry the safety claim. **The category is derived, never self-reported**
(§2.3) — `rules.resolution_category` computes exact_key > key_overlap > comment_grounded >
semantic from the evidence, because the spike's resolver reported `semantic` for every case
including the exact-key ones where it was right; a test feeds a deliberately wrong claim and
pins that it is ignored. **Post-validation demotes anything unverifiable** (§2.4): a
resolution naming a construct the vault does not have becomes `unresolved` with the violation
appended to its evidence, and the same for a `same_as` target — never a silent drop, never an
invented hub. **Same-as is first-class** (§2.2): asserted-equivalent-but-differently-keyed
produces two constructs plus a flag, and `is_merge` is false for it.

One design decision the spec left implicit, resolved conservatively and worth stating because
it shapes the workflow: **only a RATIFIED resolution steers the modeler.**
`render_resolution_prompt_section` returns `''` for anything still `proposed`. An unratified
merge reaching the prompt would make the modeler name the existing construct, which is exactly
what makes `merge_models` fold it — i.e. the merge would happen without anyone agreeing to it,
in a WP whose whole premise is that a false merge writes foreign keys into live history. So a
first run proposes, the human ratifies (`resume --resolve` / `--resolutions <file>` /
`--accept`), and a subsequent run is steered. That mirrors WP10's ratified multi-source hub,
whose regeneration is likewise a fresh run rather than an in-place resume rewrite. The cost is
one extra run on the first increment; the alternative is an unreviewed merge.

The human path gets the same guard as the model path: a `--resolve` naming a construct that
does not exist is refused with a warning rather than applied, so a typo cannot invent a hub
either. Both flag kinds (`RESOLUTION_UNRESOLVED`, `RESOLUTION_SAME_AS`) join the review queue
as aggregatable advisory items and leave `requires_signoff` unchanged — an unresolved concept
is honest output, the call WP9 made for mapping gaps.

Also collapsed here, per §2.2: `eval/resolution.py`'s `ProposedResolution` / `ResolutionResult`
are now aliases of the state models rather than parallel definitions. The answer the pipeline
emits and the answer a scorer reads must be one type, or the eval measures something the
product does not produce.

748 tests green (+20 in `tests/test_agents/test_entity_resolver.py`), ruff clean, mypy strict
clean (45 files). Two `tests/test_cli.py` pins were updated deliberately for the new
`resolutions` key in the counts dict and the decision payload (the WP11 "report" precedent).
**Open:** the §4 live acceptance runs — `false_merge_rate` 1.000 over ≥5 repeats, trap 5
reproducing `unresolved`, and the blinded probe showing accuracy falling while the merge rate
holds.

## [2026-08-01] WP29's steering path was unreachable — the checkpoint sat past the decision

Yesterday's entry closes with "a first run proposes, the human ratifies, and a subsequent run
is steered." Nothing implemented the second half. `render_resolution_prompt_section` returns
`''` for anything still `proposed`, and the only place a ratification could happen was the
sign-off checkpoint — which `graph.py` runs after `source_mapper`, i.e. after modelling, code
generation and validation. A decision made there cannot affect the model it is about, and no
later run read it back: `--existing` loads `metadata/dv_model.yml` and nothing else, and
`eval/run.py: run_chain_once` passes only that file between chain steps. So the function
returned `''` on **every reachable path**. The mechanism was built, tested and dead.

The defect is not in the code that was written; it is in a sentence the spec never wrote.
WP29 §2.5 says a ratified resolution steers the modeler by name and does not say *when* the
ratification happens. Both halves were then built correctly against their own half of that
sentence, and the gap between them was invisible to 748 passing tests, because every test
supplied the ratified state directly instead of arriving at it through the graph.

**The fix is a second `interrupt()`**, between `entity_resolver` and `dv2_modeler`
(`ResolutionCheckpointAgent`). Ratifying there is what makes the decision able to change the
model, within one run and one resume rather than two paid runs. It is inert unless an
undecided merge or same-as candidate is actually waiting — `NEW` needs no answer and
`unresolved` carries none to ratify, so greenfield, ungrounded and NEW-only runs gain no
pause, no decision record and no artifact change (`test_greenfield_inertness.py` unmoved).
Everything above the `interrupt()` is a pure filter over state, which matters more here than
at sign-off: the resolver's paid model call sits in the *previous* node, and a resume
re-executes only this one.

Three consequences worth recording because none of them is obvious from the change:

- **`eval/run.py` answered exactly one interrupt.** With two checkpoints it would have left
  every brownfield run parked at sign-off and scored a half-finished state as the outcome. It
  now resumes in a bounded loop. This is the change that unblocks the WP30 arm comparison —
  arm B's chain can now propose, ratify and model within one step.
- **`accept: True` grew teeth.** At the resolution pause it ratifies every proposed merge, so
  an unattended eval run models the resolver's proposals as though a human agreed. That is the
  configuration the arm comparison is about, and it is *not* the product's posture — recorded
  at `AUTO_RESUME_DECISION` so a later reader does not mistake one for the other.
- **A pause before modelling is not a failed model.** `_exit_unvalidated` reads
  `validation_report.passed`, still `False` by default at that point, and would have exited 3
  claiming the model failed after three attempts. Guarded on `modeling_attempts == 0`, which
  is true on exactly that path.

The interactive path gets its own prompt: the sign-off confirm reads "Accept and finalize?",
and answering yes to that at a resolution pause would have ratified a merge into live history
behind a question about finishing a run. The CLI tells the two pauses apart on typed state
(`modeling_attempts` plus pending decisions), never on where it thinks it is.

**Verified keyless:** 763 tests green (+15), ruff clean, mypy strict clean (45 files). The new guards were
mutation-checked — moving the checkpoint back behind the modeler fails exactly the two tests
that assert the ordering and the steering, and nothing else. **Not verified:** anything live.
WP29 §4's acceptance runs are still open, and the arm comparison is now unblocked but not run.

## [2026-08-01] The WP29 checkpoint, verified live — and a merge ratified at confidence 0.55

This morning's entry closed with "verified keyless; not verified: anything live." The WP30 arm-B
chain ran this evening and the mechanism is now **live-verified**, by the sharpest evidence
available rather than by inference. The chain step results carry no decision ledger, so "did the
checkpoint actually pause?" could not be answered from them — but the trace stores every prompt,
and `render_resolution_prompt_section` returns `''` by construction unless something was
ratified. So the steering section's presence *is* the proof of the pause:

```
emit_dv_model #1 (step 1, greenfield): steering section = False   <- resolver inert, correct
emit_dv_model #2 (step 2):             steering section = True

  Concepts a human has already resolved
  - `BusinessEntityID` (from employee) IS the existing **hub_business_entity**. Attach to it
    by that exact name; do not introduce a second construct for it.
  - `BusinessEntityID` (from job_candidate) is asserted equivalent to **hub_business_entity**
    but is keyed differently: model it as its OWN hub. ... do not merge the two
```

Propose → pause → ratify → steer, end to end, in one run. Both rendered forms appear, and the
greenfield step correctly shows nothing. What is verified is the **mechanism**; the resolver's
*correctness* is WP29 §4 and remains open.

**The resolver's first live data** — four calls across the extending steps, 43 concepts:

| step | concepts | merge | same_as | unresolved |
|---|---|---|---|---|
| HumanResources | 11 | 1 | 1 | 0 |
| Production | 23 | 0 | 0 | 0 |
| Purchasing | 9 | 2 | 1 | 1 |

Two behaviours the design predicted, observed for the first time. Production produced **23
concepts and zero merges** — the resolver does not reach for a merge where there is nothing to
merge. And `shipping method::Name` came back **`unresolved`** rather than guessed: the honest
degradation the Phase 2 spike measured, now in production code against a schema nobody here
authored.

**And the finding that matters more than either.** One merge was auto-ratified at **confidence
0.55** — `product::ProductID -> hub_product`. `AUTO_RESUME_DECISION`'s `accept: True` ratifies
every proposal regardless of confidence, and a merge is the direction that writes foreign
business keys into a hub holding live history. This one happens to be right —
`Purchasing.ProductVendor.ProductID` really does reference `Production.Product.ProductID` — but
that is known because a human read the schema, not because anything checked it.
`existing_construct_preservation` cannot catch a false merge: folding a concept into the wrong
hub removes nothing and re-keys nothing, so the gate passes. This was pre-registered as a blind
spot in the spec's §7.2b *before* the run; it now has a concrete instance, and it makes WP29 §4
(`false_merge_rate` over ≥5 repeats, with traps) more urgent rather than less. A second live
observation, worth stating because it is the counter-case: `job_candidate::BusinessEntityID` —
a nullable FK — became a `same_as_candidate` at 0.72 rather than a merge, which is the class
asymmetry working as designed.

The arm comparison itself (phase 1, 1 repeat each, $19.31, the charter's claim not supported at
n=1) is written up in the WP30 spec §7.3 rather than duplicated here.

## [2026-08-01] WP29 §4 cannot be run yet — three findings from looking before paying

"Let's do §4" turned out to be a work package, not a command. `brownfield_resolution` has been
sitting in `eval/datasets/` since the Phase 2 spike with an existing vault, a source schema and
a seven-trap golden — all good, all verified loadable by the production path
(`load_existing_model` returns `hub_customer`/`hub_account`; the schema loads as 8 tables). It
has never been runnable through the pipeline, and nothing said so.

**Finding 1 — the case is not wired.** No `dataset.yml`, so `--dataset brownfield_resolution`
cannot start; no `requirements.md`, so the business-key identifier has nothing to work from and
the resolver would receive an empty concept list; and `eval/run.py` never calls the resolution
scorers at all — `_score_run` dispatches the mapping scorers by the `golden_mapping.yml`
convention and has no counterpart for `golden_resolution.yml`. The spike drove the resolver
directly and never needed any of this.

**Finding 2 — the scorer cannot match the golden, and fails toward the wrong answer.** This is
the fourth appearance of the class `.claude/rules/eval.md` puts first, "score structure, not
free-form names" (WP9.2, WP14, the link-name fix):

```
pipeline emits   proposal.concept = "vic_partner::partn_nr"      (entity::field)
golden carries   concept: partner
                 source_table: vic_partner
                 source_key:   partn_nr
```

`false_merge_rate` does `expected.get(proposal.concept)` and finds nothing — and its next line
reads `if want is None or want.expected != proposal.resolution`, so an unmatched proposal is
appended to `offenders`. **Every correct merge would have been scored as a false merge**, the
gate would read 0.000 in every repeat, and we would have paid five times to learn something
untrue about the resolver. The fix is the one WP14 already established: match on
`(source_table, source_key)`, both of which the golden already carries and both of which
`split_concept_key` returns from the pipeline's key. Not made tonight — it deserves the same
care the checkpoint got, and it is the piece most likely to go wrong.

**Finding 3 — the fixture states its own answers, which is harmless to the measurement and
fatal to blinded authoring.** `source_schema.yml` labels its tables in YAML comments: "TRAP 1 —
synonym hub. This IS the existing hub_customer", "CONTROL", and for `vic_migration_altbestand`
a sentence saying the only correct answer is `unresolved`. Measured, not assumed: the parser
discards them —

```
raw file:                    7x TRAP/CONTROL
what load_source_schemas gives the pipeline:   TRAP False · hub_customer False · CONTROL False
```

— so the resolver has never seen them and no past or future score is affected. But the blinded
requirements author reads the raw file. It reported this unprompted rather than quietly writing
around it, which is the behaviour that makes the report worth having. The draft it produced is
kept, marked unusable in its own header, as the record of why. One other fixture carries the
same pattern in milder form (`messy_insurance/source_schema_enriched.yml` names which columns
seat which §4 traps); `adventureworks_*` does NOT — that grep hit is Microsoft's own column
comment "Employee who **controls** the document".

**What §4 now needs**, all keyless, before any spend: strip the annotations into a sibling file
(they duplicate `golden_resolution.yml`'s `rationale` fields), re-author blind, write
`dataset.yml`, fix the scorer matching, dispatch the resolution scorers, and test 4 and 5. Then
5 clean plus 5 blinded repeats, estimated $16-26 against the $20-40 left under the §6 ceiling.

Three times tonight something looked like a button and turned out to be a package. Each time
the looking was free and the run would not have been.

## [2026-08-01] The review of PR #16 found three guards looser than their own docstrings

All three are in code written the same day, and the first is a regression this WP introduced
rather than an old weakness it exposed. Recorded because the shape repeats: each guard checked
the *adjacent* property rather than the one its docstring claims.

**1. The exit-3 contract, broken by the new pause (normal).** `_interactive_checkpoint` rebinds
`state` from each in-process resume but was typed `-> None`, so its three callers passed the
state they had *before* the checkpoint to `_exit_unvalidated`. That was harmless while sign-off
was the only pause — a state paused there already carried the validator's final verdict, which
is exactly what the comment above the call asserted. WP29 pauses BEFORE the modeler, so the
caller's copy reads `modeling_attempts == 0` however the run ended, and **the exemption added
that same morning** (`modeling_attempts == 0`, to stop a resolution pause reporting a failed
model) then fired and returned exit 0 for a model that never validated. A wrapper script reading
the exit code — WP25 §2.2's stated purpose — would have seen success. The function now returns
its final state and the callers reassign; the stale comment is corrected rather than left to
mislead the next reader. Mutation-checked: reverting the reassignment in `run()` alone drops the
new test to exit 0.

**2. A merge target had only to EXIST, not to be a hub (nit).** Both guards — the human path's
`known` and the resolver's post-validation `names` — unioned hubs, links and satellites, so
`--resolve "x=sat_customer_details"` passed the check whose docstring says "a typo cannot invent
a hub either" and produced `is_merge=True`. Business keys anchor hubs; the modeler would have
been told to attach one to a payload table. Both now validate against hub names only. The model
is still *shown* links and satellites in its payload — that is context worth having — but a name
from that part of the inventory is no longer a valid answer.

**3. Two divergences from patterns the same file already establishes (nit).** An ambiguous
bare-label `--resolve` was dropped silently, because `resolve_concept_ref` returns `None` for
"several matches" and "none" alike; `_apply_mapping_decision`, forty lines below, warns in
exactly this case (WP32's precedent) and now so does this. And overriding a concept TO
`unresolved` pruned its review flag unconditionally, contradicting the function's own sentence
"the flag is pruned only when the decision actually resolved it" — the accept branch implements
that condition, the override branch had forgotten it, so the same intent produced different
outcomes depending on which flag the human used.

Each has a keyless guard that fails without its fix. 767 tests green (+4), ruff and mypy clean.
CI on PR #16 was green before these — the branch's first independent check, since the workflow
triggers only on pushes to `main` and on pull requests, which is why the PR was opened at all.

## [2026-08-01] WP29.1 — `brownfield_resolution` is runnable and scoreable; §4 is now only money

The three findings from this morning are closed, all keyless, no spend. What changed:

**The scorers now match on structure.** `false_merge_rate`, `resolution_accuracy`,
`new_hub_detection` and `resolution_calibration` all keyed on the golden's free-form `concept`
label while the pipeline emits `entity::field`. New `source_ref()` derives
`(source_table, source_key)` from the pipeline's key and `GoldenResolutionSet.by_source()`
keys the golden the same way — both normalised. This is `.claude/rules/eval.md`'s first rule
applied for the fourth time (WP9.2, WP14, the link-name fix).

**And the fail direction is fixed, which was the dangerous half.** An unmatched proposal used
to land in `offenders`: with nothing matching, *every correct merge scored as a false merge*
and the gate would have read 0.000 in all five paid repeats. Unmatched is now **out of
universe** — the WP14 semantics — counted and reported in `details` the way `mapping_coverage`
reports its unscored proposals, and excluded from the score. `false_merge_rate` remains a hard
property over the matched universe. Mutation-checked: reverting that one lookup to the label
fails five tests and nothing else.

**The spike-era scorer tests were re-keyed, deliberately.** Six of them built proposals keyed
by the golden's label — a shape the product has never emitted. Their kwargs still read
`partner=`, `kontakt=`, so each test still says what it is about; `_result` now translates
those to pipeline keys through the golden's own coordinates. WP29 §2.2 had already collapsed
the eval types into the product's; these tests were the last place still measuring the spike's
shape.

**The case is wired**: `dataset.yml` gates `false_merge_rate` at exactly 1.0 and
`pipeline_health` at 1.0, and deliberately leaves `resolution_accuracy` reported-not-gated —
the spike charter's split, so that honest-but-unhelpful stays distinguishable from
helpful-but-dangerous. `_score_resolution` dispatches the family by the `golden_resolution.yml`
convention, the counterpart of the mapping dispatch. The WP18 §2.1 hole is explicitly not
reproduced: a gated case whose golden vanished produces no score, and `unsatisfiable_gates`
then reports it as a **batch defect** rather than a pass — pinned by its own test, so the two
halves cannot drift apart.

**The fixture no longer states its answers, and the guard enforces that now.** The trap
annotations moved to `trap-annotations.md`; a snapshot captured from the annotated file proves
the pipeline reads exactly the same 8 tables and 23 columns as before. The requirements were
re-authored blind against the cleaned file — and the author reported that the header *I* wrote
while cleaning still named what the file was for and where the answers live. Not answers, but
enough to tell a reader the game. Removed, and `TELLS` gained "entity-resolution", "existing
bank vault", "spike" and the two filenames, so the next version of that mistake fails a test
instead of depending on a careful reader noticing. The superseded draft stays beside it with
its unusable header; records are append-only.

Verified independently rather than trusted: the new document names no trap, no entity
resolution, no existing vault and no hub. Where the schema pulls hardest — `crm_xref_partner`'s
"entspricht der nationalen Kundennummer" — it reports the comment as a statement about *values*
and pushes the entity question into an open point, which is exactly the discipline the
measurement needs.

781 tests green (+14), ruff clean, mypy strict clean. **What remains is paid and pending:** the
§4 runs themselves — 5 clean plus 5 blinded repeats, estimated $16-26 against the ~$20-40 left
under the WP30 §6 ceiling — and they run only on an explicit go.

## [2026-08-01] Correction: §4 was NOT "only money" — the first live probe says so

The entry above closes with "what remains is paid and pending". One repeat
(13 calls, ~$0.60) disproves it, and the probe was run alone precisely so that a wiring defect
would not be paid for five times. It found one, and it found something better.

**The resolver answered all seven traps correctly, on its first live run against a golden that
predates it.** Including trap 5 — the `undecidable` case the spike memo criticised the first
run for never being offered:

```
partner::partn_nr          -> hub_customer        (TRAP 1 synonym hub)        correct
contact_person::kontakt_id -> NEW                 (TRAP 2 false friend)       correct
contract_partner::vp_nummer-> NEW                 (TRAP 3 similar name)       correct
crm_customer::crm_guid     -> same_as_candidate   (TRAP 4 same-as)            correct
account::konto_nr          -> hub_account         (CONTROL easy synonym)      correct
contract::vertrag_nr       -> NEW                 (CONTROL plain new)         correct
legacy_holding::alt_nr     -> unresolved          (TRAP 5 undecidable)        correct
```

**And the scorer sees none of it, because the fix committed an hour earlier is right in the
column half and wrong in the table half.** The pipeline's concept key carries the *business*
entity the requirements name — `partner`, `legacy_holding` — not the physical table
(`vic_partner`, `vic_migration_altbestand`). The column half matches exactly, every time; the
table half never does, because the entity-to-table binding is produced by the source mapper,
which runs LATER in the graph than the resolver. There is no physical table in the concept at
the moment the resolver speaks. `false_merge_rate` therefore came back vacuous, and the WP18
machinery did its job: `GATE UNSATISFIABLE`, exit 1, no vacuous 1.0 recorded as a pass.

Two things that must not be lost when this is fixed:

- **The one "correct" answer in `resolution_accuracy` 0.143 is a false positive.** With no
  match, the scorer treats the answer as `unresolved` — and trap 5's expected answer *is*
  `unresolved`, so it scored as right having measured nothing. A matching scheme that cannot
  distinguish "answered unresolved" from "not found" will keep manufacturing that.
- **A possible false merge sits outside the golden.** The pipeline also answered for the xref
  table: `migration_assignment::crm_guid -> hub_customer`. Writing CRM GUIDs into the customer
  hub is the dangerous direction, and the golden has no entry for `crm_xref_partner`, so under
  the out-of-universe rule committed today it would pass unexamined. Whether the golden should
  cover the xref is a change to the MEASURE, not to the mechanism, and is left for the human.

Column-only matching is the obvious next move and is not obviously safe: `crm_guid` and
`partn_nr` each appear twice in this run's proposals. Not decided here.

So §4's status is: **the mechanism looks good and is not yet measurable.** Seven-for-seven is
one repeat, unscored, and read off a trace by hand — it is a reason to finish the instrument,
not a result.

## [2026-08-06] WP29.2 — the join closes on the key, and the probe turns out to hold a false merge

WP29.1 left `brownfield_resolution` runnable but unscoreable. This closes it, and the closing
produced a finding that **corrects what I wrote on 2026-08-01**.

**Route B was chosen and then measured, and it cannot work.** The plan was to join the
resolver's concept to the golden's table through the source mapper's binding
(`mappings.proposals[].entity`). Checked against all seven traps before writing any of it:

```
vic_partner::partn_nr        -> hub_customer   mapper binding *** MISSING ***   <- MERGE
vic_kontakt::kontakt_id      -> NEW            vic_kontakt              ok
vic_vertragspartner::vp_nummer -> NEW          vic_vertragspartner      ok
crm_kunde::crm_guid          -> same_as_cand.  crm_kunde                ok
vic_konto::konto_nr          -> hub_account    mapper binding *** MISSING ***   <- MERGE
vic_vertrag::vertrag_nr      -> NEW            vic_vertrag              ok
vic_migration_altbestand::alt_nr -> unresolved vic_migration_altbestand ok
```

Five of seven bind; **the two that do not are exactly the two merges**, and `false_merge_rate`
is about nothing else. The reason is structural, not incidental: a concept merged into an
EXISTING hub produces no new hub, so there is no new concept for the mapper to bind. A merge
never has a mapper binding, by construction. Route B is blind to precisely the cases the
instrument exists for.

**Built instead: route C-minimal — the business-key column is the anchor.** The claim it rests
on is that the golden judges a key's VALUE SPACE, not a table: "partn_nr is the national
customer ID and belongs to hub_customer" holds wherever that column appears. Grounded rather
than assumed — every multi-table occurrence in this case is a foreign key to its primary
occurrence and the column comments say so (`vic_kontakt.partn_nr` "FK auf vic_partner.partn_nr",
likewise `vic_vertrag.vp_nummer` and `crm_xref_partner.crm_guid`), and a foreign key shares its
target's value space by definition. `load_golden_resolution` now ASSERTS the keys are distinct,
so a later colliding entry fails loudly instead of scoring two concepts as one. Where this stops
holding — a golden keyed on a generic `name`/`id`/`code`, the WP24 shape — is written at
`by_key()`, along with why the per-entry table-scoped variant is deferred rather than built: a
field with one possible value is ceremony, not a safeguard.

**And now the correction.** On 2026-08-01 I wrote that the resolver "answered all seven traps
correctly". That is true and incomplete, and the incompleteness mattered. It answered **nine**
concepts, and one of the extra two is a false merge:

```
migration_assignment::crm_guid -> hub_customer     golden: crm_guid -> same_as_candidate
```

The xref table's `crm_guid` is the CRM's internal GUID. Trap 4 exists to say that a concept on
that key is a same-as candidate and never a merge, because the key spaces differ — merging
pushes CRM GUIDs into a hub keyed on the national customer ID. The resolver got that right for
`crm_kunde` and contradicted itself on the same key in the xref. Under WP29.1's table-based
matching the proposal was out of universe and passed unexamined; under the key anchor it is
caught. So the honest reading of the probe is **`false_merge_rate` 0.0, `resolution_accuracy`
6/7** — where the missing seventh is not a wrong answer but a *contradiction*, which
`resolution_accuracy` now reports as such rather than picking a winner (grouping proposals per
key as a LIST is deliberate; a dict would have silently dropped one of the two, and in this run
it would have dropped the false merge).

That also settles the §3 question the kick-off reserved for the human without touching the
golden: the xref needs no entry of its own, because the judgement hangs on the key.

**Kick-off §2 is fixed too.** An unmatched golden entry used to read as `unresolved` — and trap
5 expects exactly that, so it scored as correct having measured nothing. A miss is now a miss.

Verified: 785 tests green (+4), ruff clean, mypy strict clean. **Zero-cost acceptance met** —
the probe's nine answers are frozen in `tests/fixtures/resolution/probe_20260801_answers.json`
and re-scored offline, so this was measured against real model output without one new API call.
Mutation-checked: reverting the anchor to the table fails 13 tests, all of them in the two
resolution test files and nothing else. WP29.1's table-based `by_source`/`source_ref` helpers
were removed rather than left as a trap — one day old, and superseded.

**Still open:** §4 acceptance #3's blinded variant does not exist (the spike blinded by removing
column comments), and the paid runs have not been made. What §4 measures has changed shape,
though: the primary gate now reads 0.0 on stored evidence, so the first question is no longer
"does the instrument work" but "is that false merge reproducible".
