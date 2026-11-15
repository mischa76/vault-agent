# The workbench demo: AdventureWorks, five domains modelled step by step

Five finished workbench runs, one per AdventureWorks schema, each a brownfield extension of the one before,
generated on 2026-11-15 with the generator of that day (release 0.12.2 plus WP125–WP130) through the workbench API
in one paid chain (`docs/log.md`, 2026-11-15, „The demo's chain …"). Browse it without an API key:

```bash
uv sync --extra ui && (cd frontend && npm ci && npm run build)   # once
uv run vault-agent ui --root demo/workbench-adventureworks        # from any working directory
```

Do not start new runs here — use a root outside the repo for your own work.

| Run | Domain | Extends | Constructs (hubs / links / sats) | Minutes |
|---|---|---|---|---|
| `20261115T081946810763Z` | Person (greenfield) | — | 7 / 4 / 17 | 3.6 |
| `20261115T082335567302Z` | HumanResources | Person | 10 / 6 / 26 | 3.1 |
| `20261115T082653251229Z` | Production | HumanResources | 26 / 23 / 56 | 11.6 (paused at sign-off for most of it) |
| `20261115T083836408464Z` | Purchasing | Production | 29 / 29 / 65 | 3.3 |
| `20261115T084203154127Z` | Sales | Purchasing | 40 / 53 / 90 | 8.8 |

**The hub keys are the business's, not the source system's** (ADR-0021, since WP125). `hub_product` is keyed on
`ProductNumber`, `hub_customer` on `AccountNumber`, `hub_sales_order` on `SalesOrderNumber`, the reference hubs on
their names or codes; 15 of the 40 hubs sit on a single `…ID` column — 14 tables whose catalogue declares no
natural key, each disclosed in its run's report (`W_HUB_ON_TECHNICAL_KEY`), and `hub_culture`, whose `CultureID` is
a code. The demo shipped until 2026-11-15 had 28 of 40 there, `hub_product` on `ProductID` among them; it is in the
git history.

The last run's project builds on PostgreSQL with **PASS=533, ERROR=1, SKIP=3 of 537**, and a second build inserts
nothing (180 of 180 incremental models `INSERT 0 0`) — once the view in [`inferred_views.sql`](inferred_views.sql)
exists. Sixteen hubs on natural keys were counted against their source tables: each holds exactly the source's
distinct keys (plus the two zero-key rows where a link's optional participant reaches it).

**The one error is a known defect, shipped as found.** The bill of materials takes `hub_product` twice — the
assembly and its component. The component's participation got its key translation; the assembly's did not, so
`stg_product_assembly_component` hashes a `PRODUCTNUMBER` its relation does not carry, and the link with its two
satellites is skipped. The validator passed the run: its column gate does not look at a stage that reads through a
translation view (backlog C67, C68 in `docs/architecture/backlog-2026-11-candidates.md`).

**What to look at.** The Model perspective by subject area, with zoom and full screen per diagram. In the run
records' history (`run.json`, CLI equivalents) the checkpoint decisions: the first, fourth and fifth run paused on
contested hub keys (six tables — a technical primary key against a declared natural key the requirements did not
name first) and took the natural key by the bulk answer; the third run's sign-off binds a stage no rule could bind
(`--bind stg_work_order_operation=WorkOrderRouting`). In `models/staging/` 45 translation views
(`stg_<construct>_via_<relation>`): a referencing table carries the product's id, the hub is keyed on its number, and
the view joins the number in through the declared foreign key — visible SQL, not a hidden mapping. Employee, vendor,
sales person and store are subtypes of `hub_business_entity`, no hubs of their own. Six multi-active satellites;
links whose participant may be missing carry zero keys (`null_columns` in 58 staging models).

**Known open points** (backlog `docs/architecture/backlog-2026-11-candidates.md`): the bill-of-materials link above
(C67, C68); one link stage is inferred and needs the view (C64's class: a link between a composite-key hub and hubs
reached by translation).

**Building it yourself** needs the AdventureWorks tables in PostgreSQL under the schemas the generated
`sources.yml` names (`"Person"`, `"HumanResources"`, …) with `load_datetime` and `record_source` added. Microsoft's
CSVs are MIT-licensed; `uv run python -m eval.adventureworks.load_postgres --url postgresql://… ` fetches and
loads them (WP110: 68 tables, 759 239 rows). Then, after `inferred_views.sql`:
`uv run dbt deps|build --project-dir demo/workbench-adventureworks/adventureworks/runs/20261115T084203154127Z`.

**How the checkpoints were answered.** By the session that drove the chain, not by a person: the bulk answer at
the resolution checkpoint (every declared link proposal and key licence taken, contested keys left to the declared
natural key); at sign-off every contract owner `John Doe <john.doe@acme.com>`, one binding, accept.

**What was changed for publishing.** Local paths were made repo-relative. Not shipped: checkpoint databases and LLM
traces (`.vault-agent/` except `state.json`), `dbt_packages/`, `target/`, logs. The event stream is per session, so
a demo run shows no events; finished runs have no open checkpoint.
