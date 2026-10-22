# ADR-0015: Positioning — the consultant's single-user tool, or a team tool

**Status:** Proposed (draft by Claude, 2026-10-23 — the decision is the owner's)
**Date:** 2026-10-23
**Decision makers:** Mischa Eismann

## Context

The maturity review of 2026-10-22 (`reviews/maturity-review-2026-10-22.md`, backlog C20) puts the
decision before any customer pilot: is vault-agent the owner's own tool, run on his machine in an
accompanied engagement, or a tool a customer's team runs itself? Today it is unambiguously the
first, by construction, not by decision:

- The workbench binds to `127.0.0.1`, has no authentication and no notion of a user (ADR-0014).
- Run state lives per output directory: a LangGraph SQLite checkpointer and a single-slot
  `pending.json` — one run at a time per project, on one disk (ADR-0014 consequences).
- A run's folder is stored relative to the directory the workbench was started in (backlog C24),
  so a project cannot even move between machines without rewriting.
- The checkpoint records an owner as `Name <email>` that the operator types — an assertion, not an
  identity.
- Secrets (the Anthropic key, Bedrock/Vertex credentials) are read from the operator's `.env`.

The review scores operations 2.5 and market maturity 2 out of 5; most of what separates them from
the pilot threshold depends on this choice.

## Decision (proposed)

**Option A — stay the consultant's single-user tool, deliberately.** vault-agent is run by the
consultant (the owner) inside an engagement: on his machine or a customer-provided workstation,
with the customer's requirements and schemas, the output handed over as a dbt project in the
customer's git. Customer staff take part at the checkpoints in a joint session, not through their
own logins. What this requires is hygiene, not architecture: relocatable runs (C24), a documented
handover of a project folder, the data-residency route chosen per engagement (Bedrock/Vertex,
already wired), and the existing local-only binding kept as a security property.

Option B (below) stays open as a later ADR once a customer asks to run it themselves.

## Alternatives considered

- **Option A — single-user tool of the consultant.** + Matches the intended route („accompanied use
  by the consultant", review summary); no auth, tenancy or shared state to build or secure; the
  local-only binding is a strength in DACH banks and insurers (no new service in their network).
  − Scales only with the consultant's time; customers cannot run it between engagements; the
  checkpoint's owner field records names, not authenticated identities.
- **Option B — a team tool.** Authentication (OIDC against the customer's IdP), users and roles
  (modeller, reviewer, owner), a shared checkpointer (PostgreSQL instead of SQLite), concurrent runs,
  an audit trail of who decided what at a checkpoint, deployment as a container behind the
  customer's proxy. + Self-service, licensable, decisions attributable to real identities.
  − Months of work outside the product's core (DV2.0 modelling), a new attack surface, operations
  burden at the customer, and none of it measured against a real demand yet.
- **Option C — A now, B as a hosted service later.** The same as A for the next engagements, with B
  re-opened only when a customer asks for it, and then as its own ADR with that customer's
  constraints (IdP, hosting, residency).

## Consequences

If A (or C) is accepted:

- (+) The pilot threshold becomes reachable with the backlog already listed — C24, C18, C17 —
  instead of an auth/tenancy programme.
- (+) Security stays simple: no listener beyond `127.0.0.1`, secrets in the operator's `.env`.
- (−) Market maturity stays capped: the tool is a consultant's lever, not a product a customer
  buys and runs.
- (neutral) The checkpoint's owner field stays an assertion; the review queue says who was named,
  the commit history of the handed-over project says who committed.

If B is chosen instead, the next step is a spec for authentication and a shared checkpointer, and
C24 becomes part of it.

## References

- `reviews/maturity-review-2026-10-22.md` — operations and market findings, recommendation „decide the
  positioning".
- ADR-0014 — the workbench as a local, single-process application.
- `docs/architecture/deployment-residency.md` — the Bedrock/Vertex routes.
- Backlog `backlog-2026-10-candidates-2.md` (C20), `backlog-2026-10-candidates-3.md` (C24).
