# The workbench demo: AdventureWorks, five domains modelled step by step

Five finished workbench runs, one per AdventureWorks schema, each a brownfield extension of the one
before — the vault the owner modelled in the workbench and built into PostgreSQL by hand on
2026-10-19 → 22 (`docs/log.md`, „The owner's hands-on run", steps 1–8). Browse it without an API key:

```bash
uv sync --extra ui && (cd frontend && npm ci && npm run build)   # once
uv run vault-agent ui --root demo/workbench-adventureworks        # from the repo root
```

Start it **from the repo root**: each run's `run.json` stores its folder relative to the directory the
workbench was started in. Do not start new runs here — use a root outside the repo for your own work.

| Run | Domain | Extends | Constructs (hubs / links / sats) | Build on PostgreSQL |
|---|---|---|---|---|
| `20261019T204027253108Z` | Person (greenfield) | — | 7 / 5 / 17 | PASS=55 |
| `20261021T232716713739Z` | HumanResources | Person | 10 / 7 / 27 | PASS=81 |
| `20261022T133219892412Z` | Production | HumanResources | 25 / 23 / 56 | PASS=177 |
| `20261022T140746303809Z` | Purchasing | Production | 28 / 27 / 65 | PASS=208 |
| `20261022T151530662480Z` | Sales | Purchasing | 39 / 49 / 92 | PASS=334 |

**What to look at.** The Model perspective by subject area (WP80): one area in the first run, six in the
last. The resolution checkpoints' decisions are in each run's `run.json` (`checkpoints`) and CLI
equivalents. Employee, vendor, sales person and store are subtypes of `hub_business_entity` — no hub of
their own; the purchase order header carries that hub twice, as `vendor` and `employee`.

**Known findings, kept visible on purpose** (backlog `docs/architecture/backlog-2026-10-candidates-2.md`):
C11 — `sat_business_entity_pay_history`, `_email`, `_sales_quota_history` are multi-active in the model
but generated as standard satellites; C12 — `link_customer_business_entity` keeps 635 of 19 820 customers
(a NULL participant drops the row); C13 — `sat_product_assembly_component_details` re-inserts on every
run; seven link stages are inferred and need the views in [`inferred_views.sql`](inferred_views.sql).

**Building it yourself** needs the AdventureWorks tables in PostgreSQL under the schemas the generated
`sources.yml` names (`"Person"`, `"HumanResources"`, …) with `load_datetime` and `record_source` added.
Microsoft's CSVs are MIT-licensed; a loader is not in the repo yet (backlog). Then, per run in order:
`uv run dbt deps|build --project-dir demo/workbench-adventureworks/adventureworks/runs/<run>`, without
`--full-refresh`, after `inferred_views.sql`.

**What was changed for publishing.** The owner's name and address in contracts, run records and state
were replaced by `John Doe <john.doe@acme.com>`; absolute local paths were made repo-relative. Not
shipped: checkpoint databases and LLM traces (`.vault-agent/` except `state.json`), `dbt_packages/`,
`target/`, logs. The event stream is per session, so a demo run shows no events; finished runs have no
open checkpoint.
