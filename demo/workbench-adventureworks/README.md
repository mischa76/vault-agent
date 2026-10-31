# The workbench demo: AdventureWorks, five domains modelled step by step

Five finished workbench runs, one per AdventureWorks schema, each a brownfield extension of the one before,
generated on 2026-10-23 with the generator of that day (release 0.10.0 plus WP83–WP85) through the workbench API,
checkpoints answered as the owner answered them in his own build (`docs/log.md`, 2026-10-23, „The paid chain …").
Browse it without an API key:

```bash
uv sync --extra ui && (cd frontend && npm ci && npm run build)   # once
uv run vault-agent ui --root demo/workbench-adventureworks        # from the repo root
```

Start it **from the repo root**: each run's `run.json` stores its folder relative to the directory the workbench
was started in (backlog C24). Do not start new runs here — use a root outside the repo for your own work.

| Run | Domain | Extends | Constructs (hubs / links / sats) | Minutes |
|---|---|---|---|---|
| `20261022T232630984833Z` | Person (greenfield) | — | 7 / 4 / 17 | 4.2 |
| `20261022T233041709632Z` | HumanResources | Person | 10 / 6 / 27 | 2.5 |
| `20261022T233308793834Z` | Production | HumanResources | 26 / 22 / 57 | 8.2 |
| `20261022T234118699534Z` | Purchasing | Production | 29 / 27 / 67 | 3.4 |
| `20261022T234439976097Z` | Sales | Purchasing | 40 / 47 / 90 | 6.4 |

The last run's project builds whole on PostgreSQL — **PASS=340**, and a second build inserts nothing
(177 of 177 incremental models `INSERT 0 0`) — once the views in [`inferred_views.sql`](inferred_views.sql) exist.

**What to look at.** The Model perspective by subject area, with zoom and full screen per diagram. Employee,
vendor, sales person and store are subtypes of `hub_business_entity`, no hubs of their own. Ten multi-active
satellites, four of them bound to one feed of the multi-source `hub_business_entity` (email, phone, employee pay,
sales quota). Links whose participant may be missing carry zero keys (`null_columns` in the staging). In the run
records' history (`run.json`, CLI equivalents) the checkpoint decisions; in the traces (not shipped) the four
times the satellite-grain gate `E_SAT_GRAIN_NOT_UNIQUE` refused a satellite and the modeler followed its remedy.

**Known open points** (backlog `docs/architecture/backlog-2026-10-candidates-*.md`): ten link or hub stages are
inferred and need the views above (C18); a link's zero key points at a hub row only once WP86 lands (C25).

**Building it yourself** needs the AdventureWorks tables in PostgreSQL under the schemas the generated
`sources.yml` names (`"Person"`, `"HumanResources"`, …) with `load_datetime` and `record_source` added. Microsoft's
CSVs are MIT-licensed; `uv run python -m eval.adventureworks.load_postgres --url postgresql://… ` fetches and
loads them (WP110, 2026-10-31: 68 tables, 759 239 rows, the install script's own options). Then, after
`inferred_views.sql`:
`uv run dbt deps|build --project-dir demo/workbench-adventureworks/adventureworks/runs/20261022T234439976097Z`.

**What was changed for publishing.** Contract owners were given as `John Doe <john.doe@acme.com>` at the
checkpoints; absolute local paths were made repo-relative. Not shipped: checkpoint databases and LLM traces
(`.vault-agent/` except `state.json`), `dbt_packages/`, `target/`, logs. The event stream is per session, so a demo
run shows no events; finished runs have no open checkpoint. The previous demo (the owner's own build of
2026-10-22, with the data defects it found) is in the git history.
