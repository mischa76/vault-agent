# Documentation index

The catalogue of everything in `docs/`. `CLAUDE.md` holds only the invariants an agent needs in
every session; everything else lives here and is read on demand. If you are looking for *why*
something is the way it is, the answer is in a dated record below — start with the log.

**How to search.** `rg -n "<term>" docs/` beats guessing. Two shortcuts that pay off:
`grep "^## \[" docs/log.md | tail -20` for the recent timeline, and
`rg -n "E_[A-Z_]+" src/vault_agent/agents/validator.py` when you need the current gate codes
(the code is the source of truth for every count, threshold and version — see
`docs/methodology/llm-wiki-mapping.md`, deviation A).

**Ownership.** `docs/architecture/` is **append-only**: ADRs, specs, kick-offs, reviews and spike
memos are dated records whose value depends on not being rewritten. Index them, link them, quote
them — never revise them. A later insight becomes a new document or a log entry. Derived pages
(this index, the log's structure, subsystem overviews) are maintained and may be rewritten.
Because of that rule, the `type:`/`status:` frontmatter proposed in the mapping document applies
to **new** documents only; existing records were left untouched.

---

## Start here

| Document | What it is |
|---|---|
| [operations/README.md](operations/README.md) | The operations manual, 13 chapters — installation, running, HITL, gates, warehouse, troubleshooting |
| [architecture/1-architecture-overview.md](architecture/1-architecture-overview.md) | The system in one page |
| [architecture/2-multi-agent-design.md](architecture/2-multi-agent-design.md) | Agent topology and responsibilities |
| [how-requirements-become-a-model.md](how-requirements-become-a-model.md) | End-to-end walk of the actual behaviour, with its assumptions named |
| [log.md](log.md) | **The record** — every closed WP, measurement and correction, chronological, append-only |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Conventions, definition of done, and how verification levels are reported |
## The record

| Document | What it is |
|---|---|
| [log.md](log.md) | Project chronicle from 2026-06-11 onward. Entries are never rewritten; a later finding gets its own entry |
| [architecture/reviews/architecture-review-2026-06-13.md](architecture/reviews/architecture-review-2026-06-13.md) | First external-style architecture review |
| [architecture/reviews/project-review-2026-07-06.md](architecture/reviews/project-review-2026-07-06.md) | Review that produced the P1–P3 hardening batch |
| [architecture/reviews/project-review-2026-07-28.md](architecture/reviews/project-review-2026-07-28.md) | Review behind WP17–WP21 |
| [architecture/reviews/project-review-2026-07-29.md](architecture/reviews/project-review-2026-07-29.md) | Review behind WP24–WP27 |
| [architecture/scale-test-findings.md](architecture/scale-test-findings.md) | Live scale measurements and breakpoint candidates; the protocol says quote the trace, not a hunch |
| [architecture/steering-ledger.md](architecture/steering-ledger.md) | Which prompt rules the harness still needs, with the evidence and the release protocol (WP16) |
| [reality-test.md](reality-test.md) | The pipeline against a deliberately messy multi-source document |
| [pre-mortem.md](pre-mortem.md) | Red-team: where this could fail |

## Decisions (ADRs)

Append-only. Status is the ADR's own header, not this table's opinion.

| ADR | Decision | Status |
|---|---|---|
| [0001](architecture/adrs/ADR-0001-llm-choice.md) | Primary LLM = Anthropic Claude | Accepted |
| [0002](architecture/adrs/ADR-0002-orchestration-langgraph.md) | Orchestration = LangGraph | Accepted |
| [0003](architecture/adrs/ADR-0003-codegen-automatedv.md) | Code generation backend = AutomateDV on dbt | Accepted |
| [0004](architecture/adrs/ADR-0004-source-schema-grounding.md) | Ground the model in declared source schemas | Proposed |
| [0005](architecture/adrs/ADR-0005-data-contract-spec.md) | JSON-Schema data contracts, drafted producer-side | Proposed |
| [0006](architecture/adrs/ADR-0006-human-in-the-loop-review-queue.md) | HITL — review queue plus live interrupt/resume | Accepted |
| [0007](architecture/adrs/ADR-0007-automation-scope-by-layer.md) | Automation scope per Data Vault layer (the assist boundary) | Proposed |
| [0008](architecture/adrs/ADR-0008-source-to-target-mapping.md) | Source-to-target mapping — scope and premises | Accepted |
| [0009](architecture/adrs/ADR-0009-role-qualified-link-hub-references.md) | Role-qualified link hub references (self-referencing links) | Accepted |
| [0010](architecture/adrs/ADR-0010-modeler-output-scaling.md) | Modeler output scaling — streaming before staged modelling | Accepted |
| [0011](architecture/adrs/ADR-0011-satellite-source-binding-on-multi-source-hubs.md) | Satellite source binding on multi-source hubs | Accepted |
| [0012](architecture/adrs/ADR-0012-attribute-overlap-across-satellites.md) | Attribute overlap across satellites of one parent | Accepted |
| [template](architecture/adrs/ADR-template.md) | The shape a new ADR takes | — |

## Charters and spikes

A spike is measured before it is decided: charter first, throwaway prototypes, only the memo and
the eval assets survive.

| Document | What it settled |
|---|---|
| [incremental-extension-charter.md](architecture/backlog-2026-07/incremental-extension-charter.md) | Brownfield mode: extend an existing vault instead of modelling into an empty one |
| [spike-mapping-charter.md](architecture/backlog-2026-07/spike-mapping-charter.md) → [results](architecture/backlog-2026-07/spike-mapping-results.md) | LLM-first business↔source mapping beats a deterministic-first hybrid; became WP9/WP10 |
| [spike-entity-resolution-charter.md](architecture/backlog-2026-07/spike-entity-resolution-charter.md) → [results](architecture/backlog-2026-07/spike-entity-resolution-results.md) | Entity resolution is not symmetric — zero false merges is the primary metric; became WP29 |
| [roadmap-2026-07-productization.md](architecture/roadmap-2026-07-productization.md) | UI track and productization readiness |
| [deployment-residency.md](architecture/deployment-residency.md) | Deployment and data residency (Charter B) |

## Work-package specs

All under `architecture/backlog-2026-07/`. Every `wpNN-*-spec.md` has a matching
`kickoff/WPNN-*.md` — the kick-off is the brief, the spec is the contract, and the outcome is in
[log.md](log.md). [00-overview.md](architecture/backlog-2026-07/00-overview.md) is the backlog's
own overview.

| Spec | Subject |
|---|---|
| [wp1](architecture/backlog-2026-07/wp1-validator-gates-spec.md) | Four validator gates (date order, duplicate attributes, hub-HK collision, duplicate hub) |
| [wp2](architecture/backlog-2026-07/wp2-adr-author-spec.md) | ADR author: per-output artifact, no repo-layout coupling |
| [wp3](architecture/backlog-2026-07/wp3-llm-cost-spec.md) | Prompt caching, errors-only retry feedback, input-size guard |
| [wp4](architecture/backlog-2026-07/wp4-typed-validation-issue-spec.md) | Typed `ValidationIssue` instead of issue dicts |
| [wp5](architecture/backlog-2026-07/wp5-hygiene-spec.md) | Renderer ownership, dead code, logging, checkpoint pruning |
| [wp6](architecture/backlog-2026-07/wp6-eval-harness-spec.md) | Eval harness: golden datasets, deterministic scorers, optional LangSmith |
| [wp7](architecture/backlog-2026-07/wp7-staging-refinements-spec.md) | Satellite `source_table`, bound `source()` refs, seed column types |
| [wp8](architecture/backlog-2026-07/wp8-multi-role-links-spec.md) | Role-qualified link hub references (ADR-0009) |
| [wp9](architecture/backlog-2026-07/wp9-mapping-spec.md) | Business↔source mapping (ADR-0008) |
| [wp10](architecture/backlog-2026-07/wp10-multi-source-hub-spec.md) | Multi-source hub: one business key across source systems |
| [wp11](architecture/backlog-2026-07/wp11-html-run-report-spec.md) | Static HTML run report with a Mermaid model graph |
| [wp12](architecture/backlog-2026-07/wp12-interactive-resume-spec.md) | Interactive checkpoint prompt in the terminal |
| [wp13](architecture/backlog-2026-07/wp13-scale-hardness-spec.md) | Scale-hardness tooling: synthetic landscapes, usage capture |
| [wp14](architecture/backlog-2026-07/wp14-scale-mapping-coverage-spec.md) | Column-based mapping coverage for the scale cases (eval-only) |
| [wp15](architecture/backlog-2026-07/wp15-trace-capture-spec.md) | LLM trace capture — grep-able transcripts per run |
| [wp16](architecture/backlog-2026-07/wp16-steering-retest-spec.md) | Steering registry, backstop telemetry, model-release re-test |
| [wp17](architecture/backlog-2026-07/wp17-cli-crash-recovery-spec.md) | CLI crash recovery — a crashed run stays resumable |
| [wp18](architecture/backlog-2026-07/wp18-eval-gate-integrity-spec.md) | A gate must not pass on absence of evidence |
| [wp19](architecture/backlog-2026-07/wp19-contract-truncation-split-spec.md) | data_contract on the shared truncation split |
| [wp20](architecture/backlog-2026-07/wp20-name-gates-spec.md) | Construct-name gate and filesystem hardening |
| [wp21](architecture/backlog-2026-07/wp21-robustness-hygiene-spec.md) | Unreadable documents, guarded recorders, flag attribution |
| [wp22](architecture/backlog-2026-07/wp22-streaming-spec.md) | Streaming in `ForcedToolCaller` (ADR-0010) |
| [wp23](architecture/backlog-2026-07/wp23-incremental-extension-spec.md) | Brownfield mode, Phase 1 — `run --existing` |
| [wp24](architecture/backlog-2026-07/wp24-multi-source-composition-spec.md) | Multi-source composition correctness (the wrong-data class) |
| [wp25](architecture/backlog-2026-07/wp25-failed-run-outcome-spec.md) | A failed run is a first-class outcome (exit code 3) |
| [wp26](architecture/backlog-2026-07/wp26-adr-completeness-spec.md) | ADR completeness and determinism |
| [wp27](architecture/backlog-2026-07/wp27-ci-retry-hygiene-spec.md) | CI parity, retry policy honouring `Retry-After`, corrupt pointer |
| [wp28](architecture/backlog-2026-07/wp28-satellite-feed-binding-spec.md) | Satellite feed binding on multi-source hubs (ADR-0011) |
| [wp29](architecture/backlog-2026-07/wp29-entity-resolution-spec.md) | Entity resolution against an existing vault — **partially built** |
| [wp30](architecture/backlog-2026-07/wp30-adventureworks-semantic-axis-spec.md) | AdventureWorks as an independent instrument; the domain-partitioning experiment — **arm comparison open** |
| [wp31](architecture/backlog-2026-07/wp31-attribute-overlap-narrowing-spec.md) | Narrowing `E_SAT_ATTR_OVERLAP` to one payload namespace (ADR-0012) |
| [wp32](architecture/backlog-2026-07/wp32-concept-identity-spec.md) | Concept identity is (label, entity), not the label alone |

Earlier specs, before the backlog was numbered:
[poc-end-to-end-dbt](architecture/poc-end-to-end-dbt-spec.md) (the slice from requirements to a
running vault),
[review-2026-06-remediation](architecture/review-2026-06-remediation-spec.md),
[reality-test-remediation](architecture/reality-test-remediation-spec.md),
[source-schema-input](architecture/source-schema-input-spec.md),
[eff-sat-incremental-fix](architecture/eff-sat-incremental-fix-spec.md),
[data-contract-agent](architecture/data-contract-agent-spec.md).

## Methodology

The lenses this project is built with and audited against. Each mapping states adopted /
partially adopted / deviated, with the deviations named.

| Document | What it is |
|---|---|
| [dv2-rules-cheatsheet.md](methodology/dv2-rules-cheatsheet.md) | Data Vault 2.0/2.1 rules, condensed |
| [dv2-modeling-rules-spec.md](methodology/dv2-modeling-rules-spec.md) | The canon split into `[ENFORCE]` gates and `[GUIDE]` prompt rules |
| [data-contracts-approach.md](methodology/data-contracts-approach.md) | Data contracts per Sanderson/Freeman/Schmidt, applied here |
| [ireb-mapping.md](methodology/ireb-mapping.md) | IREB CPRE conventions in the requirements parser |
| [dsaf-mapping.md](methodology/dsaf-mapping.md) | Roelant Vos / DSAF as an architecture lens |
| [loops-mapping.md](methodology/loops-mapping.md) | Karpathy's LOOPS.md agent-loop rules; rule VIII is deliberately deviated from |
| [llm-wiki-mapping.md](methodology/llm-wiki-mapping.md) | Karpathy's LLM Wiki pattern — the basis for this index, the log and the shape of `CLAUDE.md` |

## Operations manual

`operations/` — [README](operations/README.md) ·
[1 Introduction](operations/01-introduction.md) ·
[2 Concepts](operations/02-concepts.md) ·
[3 Architecture](operations/03-architecture.md) ·
[4 Installation](operations/04-installation.md) ·
[5 Configuration](operations/05-configuration.md) ·
[6 Running](operations/06-running.md) ·
[7 HITL checkpoint](operations/07-hitl-checkpoint.md) ·
[8 Validation gates](operations/08-validation-gates.md) ·
[9 Warehouse](operations/09-warehouse.md) ·
[10 Observability](operations/10-observability.md) ·
[11 Evaluation](operations/11-evaluation.md) ·
[12 Troubleshooting](operations/12-troubleshooting.md) ·
[13 Glossary](operations/13-glossary.md)

Chapter 6 covers the flags including brownfield mode and the exit codes; chapter 8 is the gate
catalogue (the code remains authoritative for the current set); chapter 12 is the first stop for
an error message.

## Demos and positioning

| Document | What it is |
|---|---|
| [demos/README.md](demos/README.md) | The demo datasets |
| [demos/health-insurance-walkthrough.md](demos/health-insurance-walkthrough.md) | A full run, narrated |
| [competitive-landscape.md](competitive-landscape.md) | Market and differentiation |
| [blog/2026-06-why-data-vault-is-ready-for-agentic-ai.md](blog/2026-06-why-data-vault-is-ready-for-agentic-ai.md) | Draft article |

Runnable demos live outside `docs/`: `demo/bank_postgres/` (ungrounded, hand-authored staging)
and `demo/mapping_postgres/` (grounded and ratified, generated staging).
