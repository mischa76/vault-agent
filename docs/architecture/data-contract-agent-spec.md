# Data Contract Agent — Design Spec

> Status: **Implemented** (2026-06-14, see ADR-0005). This spec translates the methodology in
> [docs/methodology/data-contracts-approach.md](../methodology/data-contracts-approach.md) into
> concrete requirements for implementation. Source: Sanderson, Freeman & Schmidt, *Data Contracts*
> (O'Reilly, 2025). Spec-standard decision and the producer-draft inversion are recorded in
> [ADR-0005](adrs/ADR-0005-data-contract-spec.md).

## Responsibility

Generate a **draft data contract spec** for each source-to-staging data asset, plus the derived
dbt tests that let the prevention layer enforce it. The agent produces the spec and bootstraps the
producer/consumer negotiation — it does **not** finalize ownership or declare a contract
"agreed". That happens at the human-in-the-loop checkpoint.

Owns: `state.artifacts.contracts` (per the multi-agent design).

## Inputs

- The parsed requirements (`state.requirements`) — source of semantic definitions and SLAs.
- The identified entities/business keys (`state.business_keys`) — drives `primaryKey`/nullability.
- The source schema, where available (field names, types, nullability) — drives the schema block.
- Domain/ownership hints from the requirements doc, if present.

## Output: contract spec

One spec per data asset, JSON-Schema-based (emit YAML; JSON↔YAML is 1:1). Must contain:

### Contract management (required)

- `spec-version` — fixed to the spec-structure version the agent targets (start `1.0.0`).
- `name` + `namespace` — unique identifier; `namespace` groups contracts by source/domain.
- `dataAssetResourceName` — resource URL of the source asset.
- `doc` — generated description of what the contract represents and enforces.
- `owner` — **must be present, may be a placeholder** the agent flags for human assignment
  (e.g. `{"name": "TODO: assign", "email": null}`). The agent never invents a real owner.

### Schema block (required — the default deliverable)

For each field: `description`, `examples` (when inferable), and `constraints`:
`primaryKey`, `data_type` (mapped to JSON Schema types `string`/`number`/`integer`/`object`/
`array`/`boolean`/`null`), `is_nullable`, `is_updatable`, precision where relevant. Support
**union** types (`['null', 'string32']`) for optional fields and **enum** types for constrained
value sets.

Rules:
- A field identified as a business key ⇒ `primaryKey: true`, `is_nullable: false`.
- Never widen nullability beyond what the source/requirements state.
- Unknown type ⇒ flag for review rather than guessing a narrow type.

### Semantics block (optional — opt-in depth)

Value-level constraints when the requirements support them: `charLength`, `isNull`,
`isNotEmpty`, `isNullThreshold`, `min`/`max` (incl. `max: today`), regex patterns. Generate only
when grounded in a stated requirement — do not fabricate thresholds.

### Failure mode (required per rule)

Each constraint carries a **hard** vs **soft** failure flag. Default: schema/primary-key/
not-nullable violations are **hard**; semantic thresholds are **soft**. The spec must make this
explicit so the dbt/CI layer knows whether to block or alert.

## Output: dbt tests

Emit dbt tests derived from the contract (not-null, unique, accepted_values for enums, relationship
tests for keys) so prevention runs inside the existing dbt pipeline. Keep generation deterministic
where possible.

## LLM vs deterministic split

- **LLM-driven:** `doc` text, semantic-constraint inference from prose requirements, mapping fuzzy
  business statements to candidate constraints.
- **Deterministic:** type mapping, primary-key/nullability propagation from business keys, dbt-test
  emission, spec serialization/validation. This keeps the agent partly testable without an API key,
  consistent with the project's existing pattern.

## Human-in-the-loop

Surface for human confirmation (via the orchestrator) when:
- `owner` could not be inferred (always, if placeholder).
- The source schema was missing and types were inferred from prose.
- A field's nullability/key status conflicts between requirements and source schema.

## Acceptance criteria

1. Produces a schema-valid spec (validates against the spec's own `spec-version` structure).
2. Round-trips JSON↔YAML without loss.
3. Business keys correctly mapped to `primaryKey: true` + `is_nullable: false`.
4. Every constraint carries a hard/soft failure mode.
5. No invented owners, thresholds, or types — gaps are flagged, not guessed.
6. Emitted dbt tests parse (`dbt parse`) and correspond 1:1 to enforceable constraints.
7. Deterministic portions covered by unit tests that run without an API key.

## Open questions (candidate ADR)

- **Spec standard:** roll our own JSON-Schema-based spec (book's approach) vs. adopt an emerging
  open standard (e.g. the Open Data Contract Standard). The book deliberately doesn't prescribe one.
  Worth an ADR — recommend starting with the JSON-Schema approach for transparency, keeping the
  serializer swappable.
- **Consumer-first vs. producer-draft:** the book's workflow is consumer-driven; Vault-Agent infers
  a producer-side draft. Document this inversion as a deliberate design decision.
