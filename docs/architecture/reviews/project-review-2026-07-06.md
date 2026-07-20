# Project Review vault-agent — as of 2026-07-06

*Translated from the German original (2026-07-20); content unchanged.*

> **Update 2026-07-07:** P1, P2 (hardening batch) and P3 (staging generator) are implemented
> and verified (158→169 tests green; P3 additionally hardness-tested end-to-end against a clean
> PostgreSQL, see the CLAUDE.md milestone). P5 was resolved together with P1.
> The remaining points (P4, P6–P10 and the deferrals) are fully specified as
> implementation-ready work packages: `docs/architecture/backlog-2026-07/` (WP1–WP8 + kick-offs).

Scope: docs (ADRs, specs, READMEs, methodology), code (src/vault_agent, tests), demo, open
points. Verified: 151 tests green in <5 s without an API key; `ruff check .` clean; the largest
file `agents/code_generator.py` at 447 lines (no file >500). The findings H-1 (driving_key),
H-2 (model string), and M-1 (PDF/DOCX reader) listed in
`architecture-review-2026-06-13.md` are demonstrably fixed in the code — that document is
historical.

## Overall assessment

An unusually disciplined project for its maturity level. The conventions declared in CLAUDE.md
are genuinely honoured in the code: `graph.py` contains only orchestration, rules live in
`rules/dv2_rules.py`, every LLM agent uses the same injectable extractor protocol (testable
without a key), deterministic and LLM agents are cleanly separated, and the Postgres
end-to-end run is a real end-to-end proof (29 dbt tests, idempotent, end-dating verified)
rather than plausible SQL. The ADR discipline (8 ADRs, honest scope boundaries in
ADR-0007/0008, findings transparently tracked) is a distinguishing feature compared to typical
PoCs. Assessment: a solid base, production-ready for the raw-vault layer in the demonstrated
scope — with two pieces of structural debt that should be addressed before further feature
build-out (see P1/P2 below).

## Strengths

The separation of orchestration/domain logic is real, not aspirational. Forced tool-use instead
of free-text JSON parsing in all LLM calls, with re-validation via pydantic. Validator and
generator check each other (defense in depth, made explicit). Grounding is byte-identically
inert without a schema (regression protection). Test quality is high: exact code/construct
assertions, graph interrupt/resume against a real MemorySaver, no smoke tests. Documentation is
honest: gaps and deferrals are named rather than hidden.

## Weaknesses and risks (prioritised, with locations)

**1. `state.errors` as a stringly-typed multi-purpose channel — the biggest structural debt.**
Real errors, advisory flags, and warnings share one `list[str]`; the orchestrator classifies by
substring/regex (`orchestrator.py:32,41-44,65-68`) messages that `data_contract.py:255-284` and
`code_generator.py:338,400-402` produce. A reworded message breaks review-queue classification
three modules away without a test going red.

**2. Latent HITL bug: `apply_human_decision` prunes by substring** (`orchestrator.py:298-303`):
an owner assignment for asset `customer` also removes the unresolved flag for `customer_address`.

**3. LLM call path unhardened.** No `stop_reason` check: if the modeler hits `_MAX_TOKENS`
(8192), the call falls back silently to `{}` (`dv2_modeler.py:96-98`) — indistinguishable from
"the model found nothing", and a retry is burned on `E_NO_HUBS`. No retry/backoff on 429/529;
the CLI `except Exception` (`cli.py:326`) swallows the stack trace. No prompt caching despite
identical system prompts across up to 3 modeling retries (a direct Opus cost lever).

**4. Four concrete validator gaps.** (a) A duplicate attribute *within* a satellite passes
unnoticed (`validator.py:243-247`, set semantics) → the generator emits a duplicate payload
column, Postgres fails at `dbt build`. (b) Eff-sat date order is assumed, not checked: the
generator takes `attributes[0]` as start (`code_generator.py:240-241`); an LLM emitting
`["effective to", "effective from"]` produces a silently inverted eff-sat —
`effectivity_date_pair()` already exists and could check here. (c) Hub-HK collision on a shared
`source_entity` is unchecked (`code_generator.py:79-80`). (d) Same BK + same entity is not
flagged (`W_BK_COLLISION_RISK` only fires on *different* entities, `validator.py:267-268`).

**5. Generated ADRs misinform.** The caveat "specialised constructs need dedicated AutomateDV
macros not yet generated" (`adr_author.py:148-156`) has been false since nh_link/ma_sat/eff_sat
— every generated ADR for such models misleads reviewers. In addition, `_DEFAULT_ADR_DIR`
(`adr_author.py:23`) couples to the repo layout (breaks as a wheel installation) and the ADR
numbering is not idempotent (number derived from the repo directory, written into the output
directory → collisions between runs).

**6. Boilerplate and dead artefacts.** Four almost-identical Anthropic client classes (~40
lines each, e.g. `requirements_parser.py:70-105` vs. `business_key_identifier.py:55-90`);
`tools/` is empty despite the CLAUDE.md convention; the prompt files of the four deterministic
agents are never loaded; `Settings.langsmith_*`/`log_level` unused; Jinja2 declared as a
dependency but not used; renderer duplicate `cli.py:237-248` ↔ `orchestrator.py:167-179`; not a
single logging statement in src (observability only via `state.decisions`/`errors`);
`checkpoints.sqlite` grows without pruning (`cli.py:110-111`).

**7. Documentation drift.** CLAUDE.md/spec speak of "10 gates", the validator has 22 issue
codes (14 E_, 8 W_). The docstring claim "interrupt() is the first statement" is no longer true
(`orchestrator.py:315-324` — harmless today, but the protective invariant is already false).

## Open points / deliberately deferred

Staging generator (the biggest product gap: without hand-written `stg_*` models and project
scaffolding the output is not a runnable dbt project), source-dialect naming and business↔source
mapping (ADR-0008, Phase 2), DDL/DB introspection (Phase 2/3), Business Vault assist and mart
scaffolding (Phase 3), UI (deliberately after pipeline stability). `eval/` is empty scaffolding
— LangSmith is the declared next milestone but not begun; for an LLM product with hallucination
risk, the most important missing quality building block. Also open from the reality test:
contradiction reconciliation (#1), typed schema quality gates (#4), multi-role links (#5).
Multi-active sats/transactional links in the demo deliberately left open.

## Optimisation potential (prioritised)

| P | Measure | Effort | Impact |
|---|---|---|---|
| 1 | Typed `PipelineFlag` model (severity, agent, asset, kind) instead of `state.errors` strings; fixes weaknesses 1 and 2 at once | M | High — correctness + decoupling orchestrator/contracts/CLI |
| 2 | Generic `forced_tool_call` helper with `stop_reason` check and backoff retry; replaces the 4 client classes (−~120 LOC) | M | High — reliability of every LLM call |
| 3 | Staging generator (`automate_dv.stage` + sources.yml + project scaffolding from existing metadata) | L | Highest product impact — closes the "not a runnable project" gap; pure templating work, no research |
| 4 | Add validator gates: eff-sat date order, dup-attribute-in-sat, hub-HK collision, BK+entity duplicate | S/M | Medium — four real correctness holes |
| 5 | Switch `apply_human_decision` to exact asset matching | S | Medium — a real HITL bug |
| 6 | ADR author: remove the false caveat, numbering per output directory, resolve repo-path coupling | S | Medium — credibility of the generated docs |
| 7 | Prompt caching (`cache_control` on the system block) + retry feedback with errors only instead of full issues | S | Medium — direct cost lever, especially Opus |
| 8 | `ValidationIssue` (and possibly `Decision`) as pydantic models instead of `dict[str, Any]` | S | Medium — convention adherence, removes defensive parsing |
| 9 | Hygiene: merge the renderers, clean up dead prompts/`tools/`/unused deps (Jinja2 or use it), logging + `--debug` flag, checkpoint pruning; correct CLAUDE.md "10 gates" | S | Low-medium |
| 10 | Start the eval harness (LangSmith): initially the 2 demo datasets as a regression suite for the LLM agents; plus a size guard/chunking in requirements_parser | M | Strategic — the only way to make LLM regressions measurable |

## Recommended order

Harden first, then build: P1+P2 (typed flags, LLM call path) as a batch before new features —
both debts grow with every additional agent. Then P3 (staging generator) as the next product
increment, flanked by P4/P5 (correctness) and P10 (evals), before Phase-2 topics (mapping,
introspection) begin.
