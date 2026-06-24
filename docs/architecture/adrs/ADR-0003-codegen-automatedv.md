# ADR-0003: Code generation backend = AutomateDV (dbt)

**Status:** Accepted
**Date:** 2026-06-07
**Decision makers:** Mischa Eismann

## Context

Generated DV2.0 code must be production-credible and fit the modern data stack. Writing
raw SQL would be inferior to leveraging an established metadata-driven DV2.0 generator.

## Decision

Generate AutomateDV-compatible YAML metadata and dbt model files. AutomateDV (formerly
dbtvault) is the de-facto OSS standard for DV2.0 on dbt (used by McDonald's Nordic, NHS
Digital, Betway). dbt Core is the runtime; Snowflake / Fabric / DuckDB are the targets.

## Alternatives considered

- **Custom SQL templates (Jinja)** – maximum control, but reinvents what AutomateDV solved
- **Datavault4dbt** – similar concept; smaller user base and less complete docs
- **VaultSpeed (commercial)** – mature but closed; doesn't fit an open-source approach

## Consequences

- (+) Credibility – we ride a tool the audience already respects
- (+) Smaller surface area to implement and maintain
- (+) Multi-warehouse support comes for free via dbt adapters
- (-) Bound by AutomateDV's metadata schema (acceptable trade)

## References

- AutomateDV docs: https://automate-dv.com
- dbt Core: https://docs.getdbt.com

## Amendment (2026-06-17)

The platform list in the Context above is corrected: AutomateDV supports Snowflake, BigQuery,
MS SQL Server, Databricks and PostgreSQL — **not DuckDB**. The AutomateDV decision itself is
unchanged. Platform scope and the local-demo target (PostgreSQL) are governed by
[ADR-0007](./ADR-0007-automation-scope-by-layer.md) and the
[PoC spec](../poc-end-to-end-dbt-spec.md).
