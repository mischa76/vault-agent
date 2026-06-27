# ADR-0008: Source-to-target mapping — scope, premises, and the assist boundary

**Status:** Proposed
**Date:** 2026-06-27
**Decision makers:** Mischa Eismann

## Context

The two-input target (requirements *and* source schema, see
[../../how-requirements-become-a-model.md](../../how-requirements-become-a-model.md)) requires a
**mapping** between business concepts from the requirements and the physical columns of the
source system — Phase 2 of the source-schema work
([../source-schema-input-spec.md](../source-schema-input-spec.md)).
[ADR-0007](./ADR-0007-automation-scope-by-layer.md) already classifies *source identification &
profiling* as **Assist + HITL**; this ADR refines the **mapping step itself** and records the
**preconditions** under which an agent-proposed mapping can reach acceptable quality.

The decisive constraint is that the mapping's quality is **bounded by the quality and completeness
of the source-system documentation**, which in the field ranges from a structured Erwin/DDL export
with metadata to a PDF data-model diagram with none. Three hard realities follow:

- **Statistics establish structure, not intent.** Profiling can show a column is unique and
  non-null; it cannot show it is *the* business key the business means. `KD_NR` vs. `PARTNER_ID`
  vs. `LEGACY_CUST_NO` is disambiguated by source-literate humans, not by distributions.
- **Coverage is frequently unknown to the business itself.** The business sees its need
  purpose-oriented, in its own dialect, often already carrying formulas, enrichments, and manual
  product hierarchies — without certainty whether (or where) the data originates in source systems,
  or whether every element the Information layer needs is sourced at all. Much of that derived
  material has **no OLTP source**; it is born downstream.
- **Live source access is governed, not free.** In a Swiss/DACH bank or insurer, an agent does not
  get a live read on production sources to run profiling SQL (PII, production access, audit). In
  practice a sanitised extract or a metadata export is supplied — not a database login.

Without explicit premises, the mapping invites false expectations and silent errors — exactly the
credibility failure [ADR-0007](./ADR-0007-automation-scope-by-layer.md) warns against.

## Decision

**1. Mapping is assist-level, never autonomous or authoritative.** The agent proposes a *candidate*
source→target mapping with a documented evidence trail; a **source-literate human ratifies it** at
the human-in-the-loop checkpoint ([ADR-0006](./ADR-0006-human-in-the-loop-review-queue.md)). The
agent never finalises an unreviewed mapping.

**2. Mapping runs against a pre-scoped candidate set** — a requirements-scoped subset of source
objects (the *source identification* that ADR-0007 places at Assist + HITL), **not** a full
database dump.

**3. Coverage gaps are a first-class output.** Information-layer elements with no plausible source
candidate, and source elements that are derived / enriched / manually maintained (no OLTP origin →
they belong in the Business Vault or Information layer, not the Raw Vault), are **reported as gaps**
— never invented or force-fit. This mirrors the data-contract gap-flagging of
[ADR-0005](./ADR-0005-data-contract-spec.md).

**4. Live DB profiling is not a runtime capability of the pipeline.** Profiling evidence
(uniqueness, nullability, cardinality, stability, distributions) is an **input / assist artifact**:
produced ahead of time, or by an explicitly invoked, **read-only, scoped** profiling step — never
an autonomous agent logging into production sources. Organisational access and governance make
source introspection a human-governed, out-of-band step, not an automatic one.

**5. Preconditions contract.** The mapping process may be started — and its output trusted at
assist quality — only when **all** of the following hold. Where they do not, the agent runs in an
explicit **degraded mode** and must say so:

- **(a)** A requirements elicitation exists at Information-layer level: business objects, *explicit*
  business keys, relationships (cardinality + temporal behaviour), and attributes.
- **(b)** A system analysis has narrowed the **in-scope source objects** (the candidate set of #2).
- **(c)** Source documentation is available in **machine-ingestible** form — at minimum
  table/column names + types; ideally PK/FK, nullability, cardinality, comments. *Output quality is
  capped by input quality.*
- **(d)** **Profiling results** for the candidate set are available or producible (#4).
- **(e)** A **source-literate reviewer** is in the HITL loop.

When (a)–(e) are not all met, the agent must (i) proceed only as far as the available evidence
allows, (ii) mark every unverified mapping as **low-confidence**, and (iii) **surface the missing
precondition** rather than compensating by guessing.

**6. The agent compresses toil, it does not replace the analysis.** Its contribution is to generate
the profiling queries, synthesise a first-draft mapping, and attach the evidence trail — fast and
reviewable. The upstream requirements elicitation, system analysis, and final judgement remain
human-owned. *Value is speed + a prepared decision basis; authority stays with the human.*

## Alternatives considered

- **Autonomous mapping from documentation alone** (no profiling, no ratification) — rejected.
  Prose and structure cannot establish business intent; high silent-error risk.
- **A fully autonomous live-profiling agent** (logs into source DBs, profiles, maps, done) —
  rejected *as the operating model*. Technically partly feasible — reading DDL/`information_schema`,
  generating profiling SQL, and drafting a candidate mapping are each within reach — but defeated in
  practice by (i) the governance reality of production source access and (ii) the irreducible
  semantic / tribal-knowledge gap. Retained only as a **human-governed, read-only, scoped assist**
  step (#4).
- **Treat coverage gaps as failures to be filled** — rejected. The agent cannot source what is not
  there; gap-surfacing is the correct, honest behaviour.
- **No explicit premises (run it on whatever arrives)** — rejected. This is precisely what produces
  false expectations and unfocused public claims.

## Consequences

- (+) A **testable precondition contract**: pipeline behaviour and quality claims are conditioned on
  stated inputs, which defuses the "garbage in" critique and guards against over-claiming.
- (+) Phase 2 inherits ADR-0007's Assist + HITL classification and ADR-0006's ratification
  mechanism — **no new trust model** is introduced.
- (+) The **coverage-gap output** turns an awkward unknown into a deliverable that exposes upstream
  analysis gaps early — useful to the business, not embarrassing to the agent.
- (−) The pipeline **cannot promise a correct mapping from poor documentation**; it forgoes the
  "point it at any database and get a vault" pitch.
- (neutral) The interface between "profiling as a pre-step" and "profiling invoked by the pipeline"
  needs a concrete decision when Phase 2/3 are actually built; revisit then.

## References

- Two-input target & minimum inputs: [../../how-requirements-become-a-model.md](../../how-requirements-become-a-model.md)
- Source-schema input phases (Phase 2 mapping, Phase 3 staging): [../source-schema-input-spec.md](../source-schema-input-spec.md)
- Source-schema grounding (Phase 1 input producer): [ADR-0004](./ADR-0004-source-schema-grounding.md)
- Automation scope & ambition per layer (the Assist + HITL placement this refines): [ADR-0007](./ADR-0007-automation-scope-by-layer.md)
- Human-in-the-loop ratification mechanism: [ADR-0006](./ADR-0006-human-in-the-loop-review-queue.md)
- Data-contract gap-flagging (analogous honest-gap behaviour): [ADR-0005](./ADR-0005-data-contract-spec.md)
- Methodology: Linstedt & Olschimke, *Building a Scalable Data Warehouse with Data Vault 2.0*;
  Roelant Vos, DSAF; Sanderson, Freeman & Schmidt, *Data Contracts* (O'Reilly, 2025).
