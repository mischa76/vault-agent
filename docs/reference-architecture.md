# DV2.0 reference architecture — the yardstick

> **Purpose.** The Data Vault 2.0 reference architecture (Linstedt/Olschimke canon) as
> Vault-Agent's *Erfüllungsziel*: the blueprint the project measures itself against. Every element
> states what the blueprint expects, what role Vault-Agent aims for there (per
> [ADR-0007](architecture/adrs/ADR-0007-automation-scope-by-layer.md)), and how far the current
> code gets.
>
> **Ownership.** This is a **maintained page** in the sense of `docs/index.md` — it may be
> rewritten at any time and carries no historical value. The *why* behind every target lives in
> the append-only records (ADRs, specs, log). Status cells are derived from the code; when in
> doubt, the code wins — re-derive, don't trust this table. Statuses last re-derived:
> **2026-10-22** (before: 2026-08-14).

## The blueprint

The DV2.0 layer stack this project measures against:

```
Source systems
  → Staging layer          (hard rules only: hashing, load metadata, no business logic)
  → Raw Vault              (integration on business keys + history: hubs, links, satellites)
  → Business Vault         (soft rules: PIT/Bridge, business-rule sats, derived/same-as links)
  → Information delivery   (marts: dimensional structures, KPI semantics)
```

Cross-cutting, per the methodology: restartable pattern-based loads, hash-key discipline,
auditability (every row traceable to source and load), and captured decisions. ADR-0007's line
through this stack: **up to and including the Raw Vault (+ PIT/Bridge) the agent generates;
anything that is business logic it assists with transparently and never owns.**

## Coverage

Role legend (ADR-0007): **Generate** — agent produces, rule-validated · **Assist+HITL** — agent
proposes, human ratifies · **Scaffold** — agent produces structure, human owns substance ·
**Out of scope** — deliberately not this project's job.

| Element | Blueprint expects | Target role | Status today | Evidence |
|---|---|---|---|---|
| Source identification & profiling | Scoping which objects/attributes matter | Assist+HITL | **Partial** — requirements parsing (IREB-aligned), declared source schemas (ADR-0004), business↔source mapping ratified at HITL (ADR-0008); column profiles can be supplied (`--profiling`, WP9) and feed the mapper — the agent computes none itself | `requirements_parser.py`, `source_mapper.py`, `profiling.py`, wp9 |
| Staging layer | Hard rules only: hash keys, load metadata, derived columns | Generate (full) | **Achieved** — AutomateDV `stage` models, bound `source()` refs, contracts drive staging, per-feed staging on multi-source hubs, catalogue and bindings carried across brownfield steps (WP74–WP77), reserved-word columns escaped per platform (WP79). **Gap:** a link stage whose participants no rule can locate stays inferred and needs a hand-made relation (seven in the owner's AdventureWorks build; backlog C18) | `staging_generator.py`, wp7/wp28/wp74/wp77/wp79, verified on PostgreSQL and Databricks (log) |
| Raw Vault — structure | Hubs, links, satellites on business keys + history | Generate, HITL on judgement points | **Achieved** for the repertoire the generator owns (see `code_generator.py` — the code, not this table, defines it); judgement points (BK choice, grain, satellite split, entity resolution) go through the checkpoint. **Known defects** (owner's build, 2026-10-22): a multi-active satellite bound to one feed of a multi-source hub is generated as a standard satellite (C11); a link with a nullable participant drops the row while its satellites keep it — no zero keys (C12); a satellite whose key does not cover its relation's unique key is accepted (C13) | `code_generator.py`, `dv2_rules.py`, ADR-0009/0011/0012 |
| Raw Vault — loading | Pattern-based, restartable ELT | Generate | **Achieved** — runnable dbt project on AutomateDV macros; incremental and idempotent for every construct whose key matches its source's grain — measured over five brownfield steps, every earlier model `INSERT 0 0`; not for the satellites of C11 and C13, which re-insert on every run | generated dbt project, verified on Postgres (log) |
| Raw Vault — validation | Model correctness before code ships | (project addition beyond the canon) | **Achieved** — deterministic `E_` gates with bounded re-model loop; gate set owned by `validator.py` | `validator.py`, wp1 et al. |
| Business Vault — PIT / Bridge | Query-assist structures | Generate | **Open** — not built; AutomateDV 0.11.4 ships `pit` and `bridge` for all five platforms with incremental materialisations (read 2026-10-22); the concrete next feature on this axis, after C11/C13 (a PIT over a non-idempotent satellite picks an arbitrary row) | backlog C22, `docs/log.md` 2026-10-22 |
| Business Vault — business-rule sats, derived/same-as links, hierarchies | Actual business logic | Assist (propose), human owns | **Flag-only today** — the agent must not emit these as authoritative; it flags for ratification. The proposed business-rule registry does not exist yet | ADR-0007, CLAUDE.md invariant |
| Information delivery / marts | Dimensional structures + KPI semantics | Scaffold + assist | **Open** — nothing built; deliberately last | ADR-0007 roadmap gradient |
| Brownfield (extend an existing vault) | (not a canon layer, but the enterprise reality) | Generate + HITL | **Achieved, additivity verified** — `run --existing`, entity resolution and FK-derived links ratified before modelling; the five-step AdventureWorks chain, and the owner's own step-by-step build (`demo/workbench-adventureworks/`) | wp23/wp29/wp34, log |
| Decision & audit trail | Captured decisions, traceable reasoning | (project addition) | **Achieved** — ADR per modeling decision, data contracts, review queue, HTML report, traces | ADR-0005/0006, wp11/wp15 |

## Deliberately out of scope

Named so their absence reads as a decision, not a gap: **run-time execution control** of warehouse
loads (scheduling, module/batch audit — a different layer; LangGraph orchestrates the *agents*,
not the ELT), **Persistent Staging Area** (candidate ADR; architecturally heavy, outside the core
DV2.0 raw vault), **schema-on-read virtualisation** (we materialise physical dbt models), and
**BI-tool semantics** beyond mart scaffolding.

## How to read the score

The fulfilment gradient follows ADR-0007's roadmap: staging → source-scoping assist → PIT/Bridge
→ business-rule registry → mart scaffolding. Today the pattern-based front (Stage + Raw Vault,
plus validation, contracts, HITL and brownfield) is built and live-verified; the Business Vault
axis is the open frontier, starting with PIT/Bridge as the only *Generate*-class gap. Platform
reality: strategic targets Snowflake + MS Fabric; verified by real builds on PostgreSQL and, since
WP72 (2026-10-16), on Databricks; Snowflake and Fabric not yet (backlog C21; AutomateDV ships no
Fabric dialect and has no DuckDB support).
