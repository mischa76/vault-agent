# Grounded + ratified mapping demo — a running Data Vault bound to real source tables

This demo is the **runnable capture of WP9 §10.8** (`docs/architecture/backlog-2026-07/wp9-mapping-spec.md`,
acceptance #8): a **grounded + profiled + ratified** single-source run whose **generated** staging
binds to the real, business-named source tables — `customer`, `account`, `account_customer` —
rather than the inferred `raw_*` relations of the ungrounded [`demo/bank_postgres`](../bank_postgres).
It builds a running Data Vault on a local PostgreSQL, from the system's actual generator output,
with **no API key**.

> **Last verified:** 2026-07-15 on PostgreSQL 16 + AutomateDV 0.11.4. `build_vault_models.py`
> regenerated all 6 raw-vault + 3 staging models idempotently; `dbt build --full-refresh` was
> green (`PASS=12 WARN=0 ERROR=0`), incremental re-run idempotent, every vault table populated.

## Why this demo exists (and how it differs from `bank_postgres`)

Both demos build the **same fixed bank model** (2 hubs, one standard link with a driving key, 2
standard satellites, 1 effectivity satellite) through the **same real `CodeGeneratorAgent`**. They
differ only in **how the raw source is bound** — which is exactly the WP9 story:

| | `demo/bank_postgres` | `demo/mapping_postgres` (this demo) |
|---|---|---|
| Source binding | **Ungrounded** — inferred | **Grounded + ratified** — declared + mapped |
| Staging `source_model` | `raw_customer`, `raw_account`, … | `customer`, `account`, `account_customer` |
| Seeds | `raw_*.csv` | business-named `customer.csv`, … |
| `SOURCE_BINDING` flags | advisory (inferred, review) | **none** — every model bound to a declared source |
| Staging SQL | hand-authored | **generated** (incl. `sources.yml`) |

The mapping is driven by two inputs (both committed, the exact §10.8 inputs):

- a **declared, enriched source schema** — [`examples/inputs/bank_source_schema_enriched.yml`](../../examples/inputs/bank_source_schema_enriched.yml)
  (table/column names **+ types + comments**, the ADR-0008 precondition-(c) shape), and
- **profiling evidence** — [`examples/inputs/bank_profiling.yml`](../../examples/inputs/bank_profiling.yml).

## The mapping half (live) vs. the build half (this demo)

WP9 §10.8 has two halves:

1. **Mapping (needs an API key).** The live `SourceMapperAgent` reads the enriched schema +
   profiling and proposes, per concept, which physical column feeds it. On the bank case
   (2026-07-13/14) it resolved **all 9 concepts by `exact_name`, 0 gaps, 0 unresolved**, with
   correct FK-vs-anchor reasoning (`national_customer_id` → `customer`, **not** the
   `account_customer` FK). A human then ratifies (`vault-agent resume --accept`). Reproduce it
   live with:

   ```bash
   vault-agent run examples/inputs/bank_account_requirements.md \
     --source-schema examples/inputs/bank_source_schema_enriched.yml \
     --profiling     examples/inputs/bank_profiling.yml \
     --out output
   vault-agent resume --out output --accept \
     --owner "customer=<Name> <email>" \
     --owner "account=<Name> <email>" \
     --owner "account_customer=<Name> <email>"
   ```

2. **Build (deterministic — this demo).** `build_vault_models.py` hard-codes the **ratified**
   mapping (the accepted `exact_name` proposals) and the declared schema, runs the real generator
   + `rebind_staging` (the pipeline's resume path), and writes the runnable dbt project. So
   `dbt build` is re-runnable byte-identically **without a key**.

For the bank the two halves **coincide**: the source column names already equal the business
keys, so the ratified `src_nk` equals the grounded one — which is exactly why the bank is the
high-floor case. On a messy source (different physical names) the ratified binding would rename
`src_nk` to the mapped column; the mechanism is the same.

## What it builds

```
seeds/{customer,account,account_customer}.csv  ──►  models/staging/stg_*.sql  ──►  models/raw_vault/{hub,link,sat}_*.sql
(business-named toy source)                         (GENERATED automate_dv.stage,       (GENERATED automate_dv.hub/link/sat/eff_sat)
                                                     bound to the declared tables)
```

| Construct | Type | dbt model |
|---|---|---|
| `hub_customer`, `hub_account` | hub | `models/raw_vault/hub_*.sql` |
| `link_account_customer` | standard link (driving key `hub_account`) | `models/raw_vault/link_account_customer.sql` |
| `sat_customer_details`, `sat_account_details` | standard satellite | `models/raw_vault/sat_*_details.sql` |
| `sat_account_customer_eff` | effectivity satellite | `models/raw_vault/sat_account_customer_eff.sql` |

## Prerequisites

- **Python + uv** with the demo extra: `uv sync --extra demo` (dbt-core + dbt-postgres).
- **PostgreSQL 16**, native and local — the same `vault`/`vault` cluster
  [`demo/bank_postgres`](../bank_postgres/README.md#prerequisites) uses. This demo targets a
  **separate schema** (`mapping_demo`, in [`profiles.yml`](./profiles.yml)) so the two never
  collide.

## Runbook

Run from this directory. `DBT_PROFILES_DIR=.` points dbt at the bundled `profiles.yml`.

```bash
cd demo/mapping_postgres
uv sync --extra demo                              # dbt-core + dbt-postgres (once)

uv run python build_vault_models.py               # regenerate models/**/*.sql (idempotent)
export DBT_PROFILES_DIR="$PWD"
uv run dbt deps                                    # pull AutomateDV 0.11.4
uv run dbt build --full-refresh                    # seed + run + test, all green
```

Expected tail:

```
Done. PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12
```

(6 raw-vault models + 3 seeds + 3 staging views.) Re-running `dbt build` (without
`--full-refresh`) is idempotent — the incremental models add no rows.

## Verification

Every vault table is populated, and the hub carries the ratified **source-faithful** key
(`national_customer_id`, no gratuitous rename — WP9 §6):

| Vault table | Rows |
|---|---|
| `hub_customer` | 3 |
| `hub_account` | 4 |
| `link_account_customer` | 5 |
| `sat_customer_details` | 3 |
| `sat_account_details` | 4 |
| `sat_account_customer_eff` | 5 |

```bash
export PGPASSWORD=vault
psql -h localhost -U vault -d vault -c \
  "select national_customer_id from mapping_demo.hub_customer order by 1;"
```

The generated raw-vault + staging SQL and scaffolding are committed so reviewers see the
generator's grounded+ratified output without running the script; `seeds/` and `profiles.yml` are
user inputs by design. The guardrail test `tests/test_demo_mapping_postgres.py` keeps the demo in
step with the generator (bindings, zero flags, idempotency, `sources.yml` dedup).
