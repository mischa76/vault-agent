# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

- `raw_customer` → feeds `stg_customer` (expected columns: NATIONAL_CUSTOMER_ID, CUSTOMER_NAME, DATE_OF_BIRTH, LOAD_DATETIME, RECORD_SOURCE)
- `raw_account` → feeds `stg_account` (expected columns: ACCOUNT_NUMBER, BALANCE, STATUS, LOAD_DATETIME, RECORD_SOURCE)
- `raw_account_customer` → feeds `stg_account_customer` (expected columns: ACCOUNT_NUMBER, NATIONAL_CUSTOMER_ID, EFFECTIVE_FROM, EFFECTIVE_TO, LOAD_DATETIME, RECORD_SOURCE)

Every raw relation must also carry `LOAD_DATETIME` and `RECORD_SOURCE`.

## Run it

1. Define a `vault_project` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
