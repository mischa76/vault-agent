# Bank demo on Databricks (WP72)

The twin of [`../bank_postgres/`](../bank_postgres/README.md): the same model, seeds, staging
and tests, aimed at a Databricks SQL warehouse. Read that README for what the demo shows; this
one covers only what differs.

## What differs

- `dbt_project.yml` carries the seed column types in the Databricks dialect from
  `src/vault_agent/rules/platforms.py` — `string` for `varchar`, `decimal(38,18)` for
  `numeric` — and nothing else platform-specific; the raw-vault SQL is byte-identical to the
  Postgres demo's (a test keeps it so).
- `profiles.yml` reads host, HTTP path and token from the environment; catalog and schema
  default to `workspace` / `default` (the Free Edition's).
- The adapter is `dbt-databricks`, installed by the `demo-databricks` extra, which excludes
  the Postgres `demo` extra — so it lives in a second environment.

## Runbook

```bash
cd <repo>
UV_PROJECT_ENVIRONMENT=.venv-databricks uv sync --extra dev --extra demo-databricks
cd demo/bank_databricks
export DBT_PROFILES_DIR="$PWD"
export UV_PROJECT_ENVIRONMENT="$PWD/../../.venv-databricks"
uv run --no-sync --env-file ../../.env python build_vault_models.py   # regenerate (no change expected)
uv run --no-sync --env-file ../../.env dbt deps                        # AutomateDV 0.11.4
uv run --no-sync --env-file ../../.env dbt build --full-refresh        # seed + run + test
```

The checklist is the Postgres demo's (build green, second build idempotent, Phase B2
end-dating) plus the two Databricks checks of the operations manual's 9.6: a plain `dbt build`
appends rather than merges, and `BALANCE` keeps its fractions. The recorded run is in
`docs/log.md` (WP72).
