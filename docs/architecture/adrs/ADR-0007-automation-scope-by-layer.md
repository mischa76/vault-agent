# ADR-0007: Automation scope & ambition per Data Vault layer

**Status:** Proposed
**Date:** 2026-06-17
**Decision makers:** Mischa Eismann

## Context

Vault-Agent must declare *how far* it reaches across the Data Vault layer stack — Source →
Stage → Raw Vault → Business Vault → Information (marts) — and *with what division of labour*
between the agent and the human architect. Without an explicit scope the project risks two
failure modes: under-reaching (a "yet another Raw Vault generator") or, worse, over-reaching
(claiming to own business logic an LLM cannot reliably produce), which would destroy credibility
with the senior, methodology-literate audience this project targets.

A reframe drives the decision. In Inmon 3NF warehousing the intellectual heavy lifting is
**up front**: system analysis, data profiling, and the transformation rules that integrate
heterogeneous sources into one 3NF model. Data Vault 2.0 deliberately **defers** that integration
load: the Raw Vault integrates only on **business keys + historisation**; the actual business
logic lives **downstream** in the Business Vault and the Information layer (Linstedt/Olschimke;
DSAF/Vos). The work does not disappear — it moves downstream.

This has a direct consequence for automation. Data Vault cleanly separates the **pattern-based,
integration-light** front (Stage, Raw Vault) from the **logic- and judgement-heavy** back
(Business Vault business rules, marts). That separation is exactly the line between
"an agent can reliably **generate** this" and "an agent may only **assist** here". A scope that
stops at the Raw Vault has automated the *relocated-easy* part; the valuable — and risky —
frontier is how credibly the agent reaches downstream.

## Decision

Adopt a **tiered automation ambition per layer**, with three roles:

- **Generate** — the agent produces the artifact/ETL deterministically (or LLM-proposed then
  rule-validated); suitable where the work is pattern-based.
- **Assist + HITL** — the agent proposes; the human confirms via the human-in-the-loop checkpoint;
  suitable where business judgement is required.
- **Scaffold** — the agent produces structure/skeletons and flags gaps; the human owns the
  substance; suitable where business logic and semantics dominate.

| Layer | Character | Role | Rationale |
|---|---|---|---|
| **Source identification & profiling** | Judgement + deterministic statistics | **Assist + HITL** | "Relevant" is an SA/BA judgement; profiling stats are automatable. (The currently-missing `source_schemas` producer — see ADR-0004 — belongs here: propose objects/attributes from requirements, human confirms.) |
| **Stage** | Purely pattern-based (hashing, load metadata, derived columns) | **Generate (full)** | Deterministic; AutomateDV `stage`. This is the gap the PoC + a staging generator close. |
| **Raw Vault — structure** | Pattern-based, with judgement on BK / grain / satellite split / driving key | **Generate, HITL on the judgement points** | The project's current core; integration only on BK + history. |
| **Raw Vault — loading (ETL/ELT)** | Pattern-based | **Generate** | AutomateDV/dbt loading patterns. |
| **Business Vault — PIT / Bridge** | Pattern-based query-assist structures | **Generate** | AutomateDV macros; deterministic. |
| **Business Vault — business-rule satellites, derived / same-as links, hierarchies, DQ rules** | **Actual business logic** | **Assist (propose) — human owns the rule** | Highest hallucination risk; the logic is domain-specific, not pattern-based. |
| **Information / Data Marts** | Dimensional structures + KPI / metric semantics | **Scaffold + assist, human curates heavily** | Semantics, conformance and KPI definitions are business-owned. |

**The line:** up to and including the Raw Vault (+ PIT/Bridge) and their ETL, the agent
**generates**; anything that *is* business logic, the agent **assists with transparently and never
owns**.

Three governing principles:

1. **Honesty is the moat, not reach.** The defensible, high-value claim is to own the pattern-based
   pipeline end-to-end and to support the logic layers transparently, with HITL and gap-flagging —
   never to claim the agent replaces the architect's judgement on business rules. This is also the
   differentiation recorded in [../../competitive-landscape.md](../../competitive-landscape.md).
2. **Downstream, the requirement becomes the bottleneck.** The further back a layer sits, the more
   business logic would have to be present in the requirements — which it rarely is in full. The
   agent must **surface gaps, not invent** them (consistent with the data-contract gap-flagging in
   [ADR-0005](./ADR-0005-data-contract-spec.md)).
3. **Decisions and rules are captured, not buried.** Raw-Vault modeling decisions already become
   ADRs. The Business-Vault analogue is a **business-rule registry**: the agent drafts candidate
   rules, the human ratifies them — structurally mirroring the ADR trail and the HITL checkpoint
   ([ADR-0006](./ADR-0006-human-in-the-loop-review-queue.md)).

## Alternatives considered

- **Full automation across all layers (incl. Business Vault rules & marts)** — rejected. LLMs
  cannot reliably produce domain business logic; claiming so invites silent errors and destroys
  credibility with the target audience. The known agentic-data failure mode (hallucinated joins /
  rules) lands squarely here.
- **Raw-Vault-only scope** — rejected as too narrow. It automates the pattern-based part DV already
  made cheap, leaving the most time-consuming work (source scoping up front; marts downstream)
  unsupported, and offers little beyond existing dbt packages.
- **No explicit scope (let it grow organically)** — rejected. Ambiguous scope is precisely what
  produces over-claiming in public materials and unfocused roadmaps.

## Consequences

- (+) A clear, defensible positioning and an honest roadmap that follows the gradient:
  **staging generator → source-scoping assist (feed `source_schemas`) → PIT/Bridge generation →
  Business-Vault assist (business-rule registry) → mart scaffolding.**
- (+) Each layer has an explicit, testable contract for "what the agent does vs. what the human
  does", which the HITL checkpoint and ADR/contract trails already support.
- (+) Aligns the product with DV2.0 methodology: automate where the method is pattern-based, keep
  the human where the method intends judgement.
- (−) Deliberately forgoes "end-to-end push-button warehouse" marketing; the value story must be
  told as *trustworthy assistance with an automated core*, not *full autonomy*.
- (neutral) The boundary between "generate" and "assist" in the Business Vault (e.g. a computed
  satellite that is half pattern, half rule) will need case-by-case judgement; revisit as the
  Business-Vault work begins.

## References

- Competitive landscape & differentiation: [../../competitive-landscape.md](../../competitive-landscape.md)
- End-to-end PoC (Stage→Raw Vault on AutomateDV/Postgres): [../poc-end-to-end-dbt-spec.md](../poc-end-to-end-dbt-spec.md)
- Source-schema grounding (the source-scoping producer gap): [ADR-0004](./ADR-0004-source-schema-grounding.md)
- Data contracts (attribute-level governance, gap-flagging): [ADR-0005](./ADR-0005-data-contract-spec.md)
- Human-in-the-loop review queue (the ratification mechanism): [ADR-0006](./ADR-0006-human-in-the-loop-review-queue.md)
- Methodology: Linstedt & Olschimke, *Building a Scalable Data Warehouse with Data Vault 2.0*;
  Roelant Vos, DSAF; Sanderson, Freeman & Schmidt, *Data Contracts* (O'Reilly, 2025).
