# ADR-0004: Ground the model in declared source schemas

**Status:** Proposed
**Date:** 2026-06-13
**Decision makers:** Mischa Eismann

> **Amendment (2026-06-24):** the "Schema Inspector / Data Profiler" future tool now has a
> first, minimal **producer** — a declared-file loader (`vault-agent run --source-schema
> <file.yml/json>`, source-schema-input spec Phase 1) populates `source_schemas`, so this
> grounding contract is no longer inert via the CLI. DDL parsing and live DB introspection
> remain future producers; the grounding contract below is unchanged.

## Context

Until now the pipeline derived hubs, business keys, and satellite attributes purely from
requirement prose. `VaultAgentState.source_schemas` was declared but consumed by no agent,
so nothing checked a proposed business key or attribute against the columns that actually
exist in the source. For real DWH engagements the source columns are known up front, and a
business key invented from prose that does not exist in any source table is a silent defect
that only surfaces at dbt run time.

This ADR introduces an optional grounding step. It is **optional by construction**: when no
schema is declared the pipeline behaves exactly as before (no regression). When a schema is
declared it is used to flag — never to fail — proposed keys/attributes that match no source
column, and to steer the LLM toward real columns.

## Decision

**1. Schema format.** `source_schemas` becomes a typed list of `SourceTable`:

```python
class SourceTable(BaseModel):
    table: str             # the source table / entity name
    columns: list[str]     # its column names, as they appear in the source
```

In YAML/JSON a caller supplies, e.g.:

```yaml
source_schemas:
  - table: customer
    columns: [national_customer_id, customer_name, date_of_birth]
  - table: account
    columns: [account_number, opened_on, status]
```

**2. Identifier matching.** Proposed labels (business keys, attributes) are business-facing
("national customer ID") while source columns are physical ("national_customer_id"). Both
sides are matched through the same identifier normalisation the code generator already
applies (`normalize_identifier`: uppercase, collapse non-alphanumerics to `_`), so
`"national customer ID"` grounds against a `NATIONAL_CUSTOMER_ID` column. Matching lives in
`src/vault_agent/grounding.py` so the modeler, the business-key identifier, and the
validator share one definition.

**3. Two phases.**
- **Phase 1 — `[ENFORCE-lite]` (validator).** When `source_schemas` is non-empty, the
  validator emits `W_BK_NOT_IN_SOURCE` for any hub business key, and `W_ATTR_NOT_IN_SOURCE`
  for any satellite attribute, that matches no declared column. These are **warnings**: the
  schema may be incomplete, so grounding informs review, it does not fail the build.
- **Phase 2 — `[GUIDE]` (prompts).** When `source_schemas` is non-empty, the declared
  schema is rendered into the business-key and modeler system prompts so candidate keys and
  attributes are drawn from real columns. When empty, the prompt is byte-identical to today.

## Alternatives considered

- **Hard-fail on unknown columns (`E_…`)** – rejected: source schemas are frequently
  partial during early modeling, so failing would block legitimate models. Warnings keep the
  human in the loop without halting the self-correcting validation loop.
- **Free-text `source_schemas: list[str]`** – the prior placeholder. Rejected: not machine
  -checkable; we need per-table column lists to ground individual keys/attributes.
- **A dedicated profiler agent that reads live warehouse metadata** – out of scope here; the
  multi-agent design's "Schema Inspector / Data Profiler" tool can later *populate*
  `source_schemas`, but the grounding contract (this ADR) is independent of how it is filled.

## Consequences

- (+) Business keys and attributes are cross-checked against real columns when a schema is
  available; invented columns surface as review flags, not run-time failures.
- (+) The LLM is steered toward real columns, improving first-pass quality on real engagements.
- (+) Zero behavioural change when `source_schemas` is empty (regression-guarded by test).
- (neutral) Matching is normalisation-based, so a genuine column whose business label differs
  beyond punctuation/case (a true rename/alias) will still warn — acceptable as a review prompt.
- (-) `source_schemas` is now a typed structure; any future caller must supply
  `{table, columns}` objects rather than bare strings.

## References

- Remediation spec M-2: `docs/architecture/review-2026-06-remediation-spec.md`
- Multi-agent design (Schema Inspector / Data Profiler tool): `docs/architecture/2-multi-agent-design.md`
- `normalize_identifier` naming convention: `src/vault_agent/rules/dv2_rules.py`
