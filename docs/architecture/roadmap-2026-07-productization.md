# Roadmap addendum 2026-07 — UI track & productization readiness

Status: Agreed (Mischa, 2026-07-17/18) · Charters, not specs — each item gets its own
spec/kick-off when picked up.

## Context

Strategic decision: vault-agent is not a sales demo — the ambition is a tool fit for
productive use in class-1 (business-critical) projects at large DACH enterprises. Two
consequences were fixed:

1. **CLI-first invariant** (WP11 §1): pure console operation stays a complete,
   first-class mode at every stage; any web layer is strictly additive.
2. The credible adoption path is **consultant-embedded first** (own mandates, references),
   productization later — so the near-term work optimizes for trust artifacts
   (visibility, auditability, hardness evidence), not feature breadth.

## Sequence

| # | Item | Kind | Executor |
|---|------|------|----------|
| 1 | WP11 — static HTML run report | **landed 2026-07-18** | Claude Code |
| 2 | WP12 — interactive checkpoint prompt (stage 1.5) | **landed 2026-07-18** | Claude Code |
| 3 | Charter A — scale hardness test | **WP13 tooling landed 2026-07-18** (generator + eval cases + usage capture); live measurement protocol (§4) pending → `scale-test-findings.md` | Claude Code (tooling) + live runs |
| 4 | Charter B — deployment & data-residency one-pager | **done 2026-07-18** → `deployment-residency.md` | Cowork research, Mischa review |
| 5 | Charter C — competitive brief | **done 2026-07-18** → private (Nextcloud Documents, not in repo) | Cowork research, Mischa review |

B and C touch no code and can run parallel to any implementation WP. Stage 2 (HITL web
UI) stays deferred behind its own ADR and is NOT scheduled here.

## Charter A — scale hardness test ("the 300-table run")

> **Status 2026-07-18:** materialised as **WP13**; the *tooling half* (deterministic
> landscape generator `eval/scale/generate.py`, `scale_30/100/300` eval cases, per-run token/
> wall-clock/review-queue usage capture) has landed and is keyless-tested. The **live
> measurement protocol below is the maintainer's next step** — run `eval.run --dataset
> scale_30 → 100 → 300`, budget-gated, recording into `scale-test-findings.md`. A first
> candidate breakpoint is already noted there (the `requirements_parser` output cap).

*Question:* where does the pipeline break on realistic enterprise breadth — before a
customer finds out?

- **Width axis is partly done** (2026-07-15): the contract enricher survives 256-column
  tables via bounded per-field chunking, structurally unbounded. Remaining width
  unknowns: the *modeler* on very wide entities (satellite splitting behaviour around
  `SAT_WIDE_ATTRIBUTE_THRESHOLD` at 100+ attributes), and requirements docs near the
  `MAX_DOCUMENT_CHARS` (400k) guard.
- **Breadth axis is untested** and is the point: a deterministic generator script
  (`scripts/` or `eval/`) synthesizes a landscape of ~300 source tables across 2–3
  "source systems" (realistic DACH naming noise à la messy_insurance, overlapping keys
  for multi-source hubs, FK webs for the WP9.1 demotion logic) plus a matching
  requirements document and profiling file.
- **Measure, per size step (e.g. 30/100/300 tables):** wall-clock, token cost (in/out,
  cache hit effect), mapping accuracy on a sampled golden subset, review-queue usability
  (does WP-aggregation keep the checkpoint readable at hundreds of flags?), checkpoint
  DB size, contract count/time, and WHERE it first fails (LLM caps, validator noise,
  prompt size).
- **Budget-conscious:** live LLM runs cost real money — one repeat per size step,
  escalate size only while green; the generator itself and all parsing stays keyless.
- **Deliverable:** findings doc + derived WPs (each breakpoint becomes its own spec),
  golden subset promoted into `eval/datasets/` if it earns its keep.

## Charter B — deployment & data-residency one-pager

*Question:* the first thing a bank's vendor questionnaire asks — where do requirements
docs and schemas go, and under what terms?

- Research (fresh, not from memory): Anthropic API data handling (retention, no-training
  terms), Claude via **AWS Bedrock / Google Vertex in EU regions** (model availability,
  residency guarantees), and what a config switch would need — the client is already
  injectable (`ForcedToolCaller`), so document the concrete `base_url`/SDK-provider
  change, don't build it yet.
- Cover: data classes touched (requirements text, schema names, profiling stats — no row
  data by design; say so prominently), transport/at-rest handling, subprocessor chain,
  and the honest gaps (e.g. no on-prem LLM option today; note open-weights fallback
  would need an eval pass through the WP6 harness before being claimable).
- **Deliverable:** `docs/architecture/deployment-residency.md`, one page + Q&A appendix
  mapped to typical vendor-assessment questions. Demo-safe wording (public repo).

## Charter C — competitive brief (VaultSpeed, Datavault Builder, biGENiUS)

*Question:* where exactly is the defensible niche upstream of the established
metadata-driven automation tools?

- Researched live (websites, docs, release notes — not training memory); WhereScape as a
  fourth reference point. Matrix along the pipeline: requirements intake → model
  derivation → source mapping → code generation → HITL/governance/audit → platform
  targets → pricing/segment signals. Explicitly capture each vendor's *AI claims* and
  what they actually automate (model-given vs. model-derived).
- Working hypothesis to verify or kill: vault-agent's differentiation is the governed
  requirements→model→mapping step (HITL ratification, ADR trail, honest gaps), not code
  generation — the established tools start from a model that already exists.
- **NOT for the public repo** (competitive positioning of named vendors in a public
  portfolio looks off): deliverable lives outside vault-agent, e.g. the private
  Documents folder; only neutral positioning language may flow back into README/pitch.

## Recorded follow-ups already noted elsewhere

Model diff between runs (WP11 §8), stage-2 HITL web UI (ADR-gated), vendored-mermaid
offline mode (WP11 §8).
