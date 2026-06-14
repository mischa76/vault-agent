# ADR-0005: A JSON-Schema-based data-contract spec, drafted producer-side

**Status:** Proposed
**Date:** 2026-06-14
**Decision makers:** Mischa Eismann

## Context

The Data Contract agent generates a draft contract for each source-to-staging data asset,
plus the dbt tests that let the prevention layer enforce it (see
`docs/architecture/data-contract-agent-spec.md`). Two design questions, flagged as open in
that spec, had to be resolved before implementation:

1. **Which spec standard?** Roll our own JSON-Schema-based spec (the book's approach) versus
   adopt an emerging open standard such as the Open Data Contract Standard (ODCS). The book —
   Sanderson, Freeman & Schmidt, *Data Contracts* (O'Reilly, 2025) — deliberately does not
   prescribe one.
2. **Whose draft?** The book's workflow is *consumer-driven*: a consumer requests guarantees
   and the producer agrees them. Vault-Agent has no human consumer in the loop at generation
   time; it works forward from a requirements document.

## Decision

**1. Spec standard — roll our own, JSON-Schema-based.** The contract is a typed pydantic
model (`src/vault_agent/models/contract.py`) serialised to a plain dict; JSON ↔ YAML is 1:1,
so it round-trips losslessly. Structure follows the book: a contract-management header
(`name`, `namespace`, `dataAssetResourceName`, `doc`, `owner`), a required `schema` block of
typed fields (`spec-version` and `schema` are emitted via pydantic aliases), and an optional
per-field `semantics` block of value-level constraints. Field types map to JSON Schema base
types, support unions (`['null', 'string']`) for optionals, and `enum` for constrained sets.

Rationale: transparency and control. We own every field, can validate the contract against
our own model, and keep the serializer swappable — an ODCS (or other) exporter can be added
later without touching how the agent reasons. Adopting an external, still-evolving standard
now would couple us to its churn for no immediate interoperability gain (there is no external
consumer yet).

**2. Producer-side draft (deliberate inversion).** The agent infers a producer-side *draft*
from the requirements and bootstraps the negotiation; it never declares a contract "agreed".
The human-in-the-loop checkpoint (via the orchestrator) is where ownership is assigned and
the contract is accepted. This inverts the book's consumer-first flow and is intentional: the
draft gives the producer and consumer a concrete artifact to negotiate from.

**3. Hard vs soft failure modes.** Every constraint declares whether a violation **blocks**
(hard) or **alerts** (soft). Schema / primary-key / not-null breaches default to hard;
semantic thresholds default to soft. This is what the dbt/CI layer reads to decide gate vs
warn.

**4. LLM vs deterministic split** (consistent with the project's other agents, so the core is
testable without an API key):
- *Deterministic*: asset/field selection, business-key → `primaryKey: true` /
  `is_nullable: false` propagation, failure-mode assignment, the placeholder owner, dbt-test
  emission, and serialization.
- *LLM-driven* (injectable `ContractEnricher`): `doc`, field descriptions/examples, type
  inference from prose, and semantic constraints.

**5. Never invent — flag instead.** A type that cannot be determined is emitted as `unknown`
and flagged; the owner is always a placeholder (`{"name": "TODO: assign", "email": null}`)
and flagged; a missing source schema is flagged (types inferred from prose). Gaps surface as
human-review flags, never as confident guesses.

## Alternatives considered

- **Adopt ODCS now** — rejected for the moment: external dependency on an evolving standard,
  less control over structure, and no consumer yet to benefit from interoperability. Revisit
  when an external catalog/consumer needs it; the swappable serializer keeps this cheap.
- **Consumer-first workflow (as in the book)** — not applicable at generation time; there is
  no human consumer in the loop. Captured as the deliberate producer-draft inversion above.
- **Ask the LLM for nullability / primary keys** — rejected: these follow deterministically
  from the already-identified business keys, so computing them keeps the contract reproducible
  and the core unit-tested without a key.

## Consequences

- (+) Transparent, fully-typed contracts validated against our own model; reproducible
  deterministic core runs in CI without an API key.
- (+) dbt schema tests (`unique`, `not_null`, `accepted_values`) are derived 1:1 from
  enforceable constraints and land beside the generated models, using the same normalised
  column names as the code generator.
- (+) Serializer is swappable — an ODCS export is an additive change, not a rewrite.
- (neutral) The contract is a *draft*: ownership and agreement are deferred to the
  human-in-the-loop checkpoint (orchestrator), still to be built.
- (-) Source schemas (`SourceTable`) carry column names but not types/nullability, so types
  are LLM-inferred and flagged when uncertain rather than read structurally. A future schema
  profiler can populate richer source metadata to tighten this.

## References

- Design spec: `docs/architecture/data-contract-agent-spec.md`
- Methodology: `docs/methodology/data-contracts-approach.md` (Sanderson, Freeman & Schmidt,
  *Data Contracts*, O'Reilly 2025)
- Source-schema grounding (reused for business-key → primary-key matching): ADR-0004
- Code-gen identifier normalisation (shared with dbt-test column names): ADR-0003,
  `src/vault_agent/rules/dv2_rules.py`
