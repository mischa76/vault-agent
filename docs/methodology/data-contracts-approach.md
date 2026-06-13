# Data Contracts – Vault-Agent's Approach

> **Primary source:** Chad Sanderson, Mark Freeman & B.E. Schmidt, *Data Contracts:
> Developing Production-Grade Pipelines at Scale* (O'Reilly, 2025). Page/chapter references
> below are to the O'Reilly first edition.

## What a data contract actually is (and isn't)

A data contract is an **architecture pattern**, not a file format. Sanderson et al. define it
as "an agreement between data producers and consumers that is established, updated, and
enforced via an API" (Preface). The contract *spec* (the YAML/JSON file) is only one piece of
that pattern — "the spec is not a data contract itself" (Ch. 5). The contract is the whole loop:
expectations codified as version-controlled code, compared against real metadata, with
detection and automated alerting wired into the developer workflow.

This matters for Vault-Agent: the Data Contract Agent generates the **spec**, but the spec only
becomes a *contract* once an owner is assigned and a producer confirms it is viable. The agent
produces a high-quality **draft**; the human-in-the-loop step closes the loop.

## The four components

The book decomposes the architecture into four components (Ch. 4–6). Vault-Agent operates
mainly in the first two and emits artifacts that feed the second two:

1. **Data assets** — the databases/streams put under contract. Of the four asset categories
   (analytical DB, transactional DB, event sourcing/streams, first-party-data-on-third-party-
   platform), Vault-Agent's relevant boundary is the **transactional → analytical** pipeline,
   which the authors explicitly recommend as the best place for most organizations to *start*
   ("both software-engineering and data teams are active stakeholders … highest probability of
   preventing major data quality issues", Ch. 4). This is exactly Vault-Agent's source-to-
   staging boundary.
2. **Contract definition** — the spec, the business logic it codifies, and the schema
   registry / data catalog it is compared against. This is the Data Contract Agent's core
   output. Detailed below.
3. **Detection** — extracting and analyzing changes to data-asset metadata (schema at the code
   level, semantics at runtime). Out of scope for the agent to *implement*, but the generated
   contract is what detection checks against.
4. **Prevention** — automated enforcement in the developer workflow (CI/CD, version-controlled
   review, monitoring/alerts). Vault-Agent emits dbt tests derived from the contract so that
   prevention can run in the dbt pipeline.

## The contract spec — concrete structure

The book recommends building the spec on **JSON Schema paired with YAML** — technology-agnostic,
human-readable, semantically versioned, covering both schema *and* semantics (Ch. 5). The spec
breaks into three parts:

### 1. Contract management (meta-metadata)

| Field | Meaning |
|---|---|
| `spec-version` | Version of the spec *structure* itself; bumps as the spec format evolves |
| `name` | User-defined contract name; `name` + `namespace` form a unique identifier |
| `namespace` | A collection of contracts — a higher-level "folder" |
| `dataAssetResourceName` | URL path of the data source under contract (e.g. `postgres://db/<name>.<table>`) |
| `doc` | What the contract represents and enforces |
| `owner` | Individual or group + contact, notified on violation or change request |

The `owner` and `doc` fields are what turn institutional/tribal business logic into discoverable,
version-controlled code — the authors stress this is the point of the management section, not an
afterthought.

### 2. Data schema

Maps fields to JSON Schema types (`string`, `number`, `integer`, `object`, `array`, `boolean`,
`null`), plus **union** typing (e.g. `['null', 'string32']`) and **enum** typing for constrained
value sets. Per-field constraints in the book's example include `primaryKey`, `data_type`,
`numeric_precision`, `is_nullable`, `is_updatable`. Schema enforcement is "the first use case
implemented on a company's data contract journey" — protect the obvious, disastrous upstream
changes first.

### 3. Data semantics (constraints on values)

Beyond shape, constraints on the data itself and conditional (if-else) logic across fields, e.g.
`charLength`, `isNull`, `isNotEmpty`, `isNullThreshold: 0.8`, `max: today`. This is the "walk/run"
stage — added once schema enforcement is in place.

A trimmed version of the book's reference spec (Ch. 5, Met Museum example):

```json
{
  "spec-version": "1.0.0",
  "name": "object-images-contract-spec",
  "namespace": "met-museum-data",
  "dataAssetResourceName": "postgresql://postgres:5432/postgres.object_images",
  "doc": "Data contract for the object_images table …",
  "owner": { "name": "Data Engineering Team", "email": "data-eng@museum.org" },
  "schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "table_name": "object_images",
    "properties": {
      "object_id": {
        "description": "Identifying number for each artwork (unique key field)",
        "constraints": { "primaryKey": true, "data_type": "integer", "is_nullable": false }
      }
    }
  }
}
```

## The contract workflow is consumer-driven

A central, repeated point: contracts **start with the consumer**, who is the only stakeholder who
understands the downstream use case; the producer then **confirms viability**. The book's seven
steps (Ch. 4):

1. Data constraint identified by the data consumer.
2. Consumer requests a contract for the asset.
3. Producer confirms the contract is viable (and adjusts).
4. Contract confirmed as code (the "forcing function" — the most important step, because it
   forces producers and consumers to communicate).
5. Producer opens a PR to change the asset.
6. CI/CD automatically checks whether the change violates a contract.
7. On result: (a) owners notified, failure protocol runs; or (b) asset updated downstream.

Implication for Vault-Agent: an auto-generated contract is a **producer-side draft inferred from
requirements**, which inverts the book's consumer-first ideal. The honest framing is that the
agent bootstraps the spec and the *negotiation*, rather than replacing it — the HITL step is where
a human assigns ownership and a producer/consumer confirms viability.

## Hard vs. soft failure

A violation is **not** automatically a hard block. The spec itself should declare whether a given
violation is a **hard failure** (block the merge) or a **soft failure** (alert downstream owners
but allow the change — e.g. urgent hotfixes). Vault-Agent's generated contracts should carry a
per-rule failure mode so the downstream dbt/CI layer knows how to react.

## Maturity curve — crawl, walk, run

Adoption follows three stages — **awareness → collaboration → ownership** (Ch. 4) — and the
authors explicitly recommend a "crawl, walk, run" path (Ch. 5): start with **schema** enforcement
on a small set of **tier-one data products**, then add **semantic** constraints, then advanced
governance (PII enforcement, lineage-based impact analysis, profiling thresholds). Vault-Agent
should generate the schema layer by default and treat semantic/governance constraints as opt-in
depth, not table stakes.

## How this maps onto Vault-Agent

- **Where contracts live:** the source-to-staging boundary (transactional → analytical) — aligned
  with the book's recommended starting point.
- **What the Data Contract Agent emits:** a JSON-Schema-based spec (contract management + schema,
  with optional semantics), plus derived dbt tests for the prevention layer.
- **What stays human:** owner assignment and producer/consumer confirmation of viability, surfaced
  at the orchestrator's human-in-the-loop checkpoint.
- **Versioning:** the contract spec is semantically versioned; contract evolution is expected and
  tracked in git.

## Source note

An earlier version of this file, CLAUDE.md, and the README cited *Driving Data Quality with Data
Contracts* (Manning) as a placeholder. The book actually in the project library — and the basis for
this document — is **Sanderson, Freeman & Schmidt, *Data Contracts* (O'Reilly, 2025)**. All three
references have been updated to match (2026-06-11).
