# The workbench demo: AdventureWorks, five domains modelled step by step

Five finished workbench runs, one per AdventureWorks schema, each a brownfield extension of the one before,
generated on 2026-11-15 with the generator of that day (release 0.12.2 plus WP125–WP133) through the workbench API
in one paid chain (2026-11-15). Browse it without an API key:

```bash
uv sync --extra ui && (cd frontend && npm ci && npm run build)   # once
uv run vault-agent ui --root demo/workbench-adventureworks        # from any working directory
```

Do not start new runs here — use a root outside the repo for your own work.

| Run | Domain | Extends | Constructs (hubs / links / sats) | Minutes |
|---|---|---|---|---|
| `20261115T111031038199Z` | Person (greenfield) | — | 7 / 5 / 17 | 4.1 |
| `20261115T111446973899Z` | HumanResources | Person | 10 / 7 / 28 | 3.5 |
| `20261115T111823849877Z` | Production | HumanResources | 26 / 23 / 61 | 9.4 (about one of them paused at sign-off) |
| `20261115T112757570638Z` | Purchasing | Production | 29 / 28 / 72 | 2.6 |
| `20261115T113044562235Z` | Sales | Purchasing | 40 / 48 / 98 | 6.5 |

**The hub keys are the business's, not the source system's** (ADR-0021, since WP125). `hub_product` is keyed on
`ProductNumber`, `hub_customer` on `AccountNumber`, `hub_sales_order` on `SalesOrderNumber`, the reference hubs on
their names or codes; 15 of the 40 hubs sit on a single `…ID` column — 14 tables whose catalogue declares no
natural key, each disclosed in its run's report (`W_HUB_ON_TECHNICAL_KEY`), and `hub_culture`, whose `CultureID` is
a code. The demo shipped until 2026-11-15 had 28 of 40 there, `hub_product` on `ProductID` among them; it is in the
git history.

**The last run's project builds whole on PostgreSQL: PASS=575, ERROR=0, SKIP=0 of 575**, and a second build
inserts nothing (186 of 186 incremental models `INSERT 0 0`) — once the two views in
[`inferred_views.sql`](inferred_views.sql) exist. Sixteen hubs on natural keys were counted against their source
tables: each holds exactly the source's distinct keys (plus the two zero-key rows where a link's optional
participant reaches it).

**The bill of materials** is the case to look at. `link_product_assembly_component` takes `hub_product` twice —
the assembly and its component — from a table that carries two product ids and no product number. Its stage reads
one translation view with two joins through `Product` (`models/staging/stg_product_assembly_component_via_…`):
2 484 link rows, the distinct (assembly, component, unit) of the table's 2 679 rows, every key joining
`hub_product`. Its detail satellite is multi-active on `StartDate` (2 679 rows): the validator refused the first
draft, whose key did not cover the table's unique key, and the modeler followed the remedy
(`E_SAT_GRAIN_NOT_UNIQUE`; read from the run's traces, which are not shipped). The chain run a few hours earlier
shipped this link unbuildable (closed by WP131–WP133).

**What else to look at.** The Model perspective by subject area, with zoom and full screen per diagram. In the run
records' history (`run.json`, CLI equivalents) the checkpoint decisions: the first, second, fourth and fifth run
paused on contested hub keys (eight tables — a technical primary key against a declared natural key the
requirements did not name first) and took the natural key by the bulk answer. In `models/staging/` 43 translation
views (`stg_<construct>_via_<relation>`): a referencing table carries the product's id, the hub is keyed on its
number, and the view joins the number in through the declared foreign key — visible SQL, not a hidden mapping.
Employee, vendor, sales person and store are subtypes of `hub_business_entity`, no hubs of their own. Eleven
multi-active satellites; links whose participant may be missing carry zero keys (`null_columns` in 53 staging
models).

**Known open points.** Two stages are inferred and
need the views: `stg_work_order_operation` (C64: the link takes `hub_product`, and `WorkOrderRouting` declares no
foreign key to `Product` — since WP136, 2026-11-16, the review names that key, and a run that accepts it as an
inferred key binds the stage; this demo was generated before that), and `stg_product_subcategory` — the modeler named the link between product and subcategory
`link_product_subcategory`, the name rule tried the table of that name, the column check refused the binding
(the review queue's `binding-rejected` decision), and no rule then looked for the relation the link really reads
(`Product`; C71). Later runs rename such a link after its hubs and bind it (WP135, 2026-11-16); this demo was
generated before that.

**Building it yourself** needs the AdventureWorks tables in PostgreSQL under the schemas the generated
`sources.yml` names (`"Person"`, `"HumanResources"`, …) with `load_datetime` and `record_source` added. Microsoft's
CSVs are MIT-licensed; `uv run python -m eval.adventureworks.load_postgres --url postgresql://… ` fetches and
loads them (WP110: 68 tables, 759 239 rows). Then, after `inferred_views.sql`:
`uv run dbt deps|build --project-dir demo/workbench-adventureworks/adventureworks/runs/20261115T113044562235Z`.

**How the checkpoints were answered.** By the session that drove the chain, not by a person: the bulk answer at
the resolution checkpoint (every declared link proposal and key licence taken, contested keys left to the declared
natural key); at sign-off every contract owner `John Doe <john.doe@acme.com>`, no binding, accept.

**What was changed for publishing.** Local paths were made repo-relative. Not shipped: checkpoint databases and LLM
traces (`.vault-agent/` except `state.json`), `dbt_packages/`, `target/`, logs. The event stream is per session, so
a demo run shows no events; finished runs have no open checkpoint.
