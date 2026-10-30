---
type: backlog
status: proposed
updated: 2026-10-23
---

# Backlog candidates of October 2026, part 3 — recorded so far only in the log

Status: **Proposed, not prioritised** (2026-10-23) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates-2.md` (C8–C21, append-only). C22–C24 were first written into
`docs/log.md` on 2026-10-22 and were findable nowhere else; C25 is the open half of C12. „C" stands for
*candidate*: a finding or idea, not yet a work package; a candidate the owner approves gets a WP number, a
spec with pre-registration and guards first. Status of the earlier candidates: C11 → WP84, C12 → WP83
(phase 1), C13 → WP85, C14–C16 done without a WP, C4 reserved as WP82.

## C22 — PIT and bridge generation

**Correction recorded with it:** part 2 listed PIT/Bridge under „not taken up" with ADR-0007 as the reason —
wrong. ADR-0007's layer table puts „Business Vault — PIT / Bridge" on the **Generate** side and names
„PIT/Bridge generation" as a step of its roadmap gradient (log, 2026-10-22, „Correction: ADR-0007 …").
AutomateDV 0.11.4 ships `pit` and `bridge` for all five platforms with incremental materialisations (read in the
installed package). vault-agent generates neither. Shape of a WP: an as-of-dates model (a date spine;
`dbt_utils` is a dependency already), a PIT per hub with two or more satellites — deterministic from the
model — and bridges along link paths, which need a path choice from the requirements, ratified by a human.
Before specifying: AutomateDV's ghost-record handling for PIT lookups; a PIT over a non-idempotent satellite
picks an arbitrary row, which WP84/WP85 have now closed for the known classes. Next on ADR-0007's roadmap.

## C23 — An AdventureWorks data loader in the repository

The demo `demo/workbench-adventureworks/` and every chain build need Microsoft's AdventureWorks CSVs (MIT)
loaded into the warehouse under the schemas the generated `sources.yml` names, with `load_datetime` and
`record_source` added; the loader so far was a session script (`pg_load_all.py`, log 2026-10-18), not in the
repo, with special cases (`ProductReview`'s multi-line records, `Document`'s CRLF, the hierarchy root's empty
key). Candidate: a loader under `eval/adventureworks/` that downloads the CSVs, applies the DDL's column order
and types, and loads PostgreSQL (Databricks as a second target), so anyone can build the demo, not only browse it.

## C24 — Relocatable runs

`run.json` stores `out_dir` relative to the directory the workbench was started in (`runs.py`:
`Path(meta["out_dir"])`), and a brownfield run names its predecessor the same way. A project root therefore
cannot be moved or copied; the demo works only started from the repository root with exactly
`--root demo/workbench-adventureworks`. Candidate: resolve a run's folder from the store
(`ProjectStore.run_dir(project, stamp)`) and keep `out_dir` for display and CLI equivalents only.

## C25 — Zero-key rows in the hubs (C12, phase 2)

Since WP83 a link row with a missing optional participant carries the zero key `hash('-2')` — but no hub row
carries that key, so a join from such a link to its hub must be an outer join and referential tests would fail.
DV2.0 puts `-1` (required, missing) and `-2` (optional, not applicable) records into every hub. AutomateDV has
ghost records for satellites only. Candidate: a small generated zero-key model per hub, typed like the hub's key,
added to the hub's `source_model` list — or a documented post-hook; the hub-key type is the open design question
(the contracts carry declared types; the warehouse's may differ).

## C26 — Homonym keys (recorded here for completeness; closed by WP89, 2026-10-23)

Found by WP86's measurement (`docs/log.md`, 2026-10-23): a link participation read from a column that shares the hub
key's name while the relation declares a *different* foreign key to the hub's table (`SalesOrderHeader.AccountNumber`,
a financial account, beside `CustomerID → Customer`); all 31 465 rows of `link_sales_order_customer` joined no
customer. WP89 lets the ratified key's translation win and projects the translated key beside the homonym.

## C27 — Source catalogue and profiling read directly from the source system (the owner's idea, 2026-10-24)

Today the three inputs — requirements, declared source schema, profiling — are YAML someone writes; for AdventureWorks
the schema was parsed from Microsoft's DDL script (`eval/adventureworks/extract.py`), which a customer does not have.
Candidate, in four stages of rising risk:

1. **Catalogue** (deterministic, metadata only): connect to the source database and read tables, columns with types,
   primary and unique keys, declared foreign keys and column comments into the house `source_schema.yml`, which the
   loader already validates. Implementation question for an ADR: SQLAlchemy's `Inspector` (one reader, dialects for
   PostgreSQL, SQL Server, Oracle, DB2 via `ibm_db_sa`, HANA via `sqlalchemy-hana`, Snowflake, Databricks, BigQuery)
   against hand-written catalogue queries per vendor (`information_schema`; Oracle `ALL_*`; DB2 `SYSCAT.*`; HANA
   `SYS.*`). Verification tiers: A — PostgreSQL, SQL Server, Oracle XE, run as containers in a dedicated small VM on the
   home server (Docker belongs in a VM there, not in the dev LXC); B — DB2, HANA, Snowflake, BigQuery written from
   documentation and marked unverified until a system is at hand; C — SAP ERP/S/4, a package of its own: the metadata
   lives in the ABAP Dictionary (`DD02L`, `DD03L`, `DD08L`/`DD05S`, texts in `DD02T`/`DD04T`), foreign keys are
   dictionary relationships, not database constraints, and the text tables would give the modeler descriptions the
   cryptic field names lack.
2. **Profiling as a selectable list of deterministic checks** — row count, null and distinct ratios, min/max, lengths,
   value patterns, candidate keys by uniqueness — into the profiling format the WP9 mapper reads. Touches data, not
   only metadata: sampling, no raw values in artefacts beyond patterns, an explicit per-run consent; belongs in
   `deployment-residency.md`.
3. **Key inference** from uniqueness and inclusion dependencies (every value of A occurs in B) — the `none` cases of
   C18. An inference, not a declaration: its own class („inferred key"), ratified at the checkpoint, never binding
   on its own (WP34's inertness stays).
4. **Requirements from the catalogue** — a drafted requirements skeleton, LLM text marked as such: C1's source-driven
   mode and its ADR.

Order proposed: stage 1 after the data packages and before C23 (the AdventureWorks loader is its natural
cross-check); stages 3 and 4 need the ADR together with C1; the source-system VM is a server task
(`home-server-eigenbau`, `PLAN_vault-dev_Container.md` §2).

## C28 — A hub-and-link stage whose participation key lives a join away (found by WP82, 2026-10-24)

The one hand view the paid chain's last step still needs after WP82, and the owner's `raw_sales_order_currency_rate`:
`stg_sales_order` serves `hub_sales_order` and `link_sales_order`, and the link's currency-rate participation is keyed
on `CurrencyRate`'s natural key (`CurrencyRateDate`, `FromCurrencyCode`, `ToCurrencyCode`) while `SalesOrderHeader`
carries only the surrogate `CurrencyRateID` — a translation (WP36, ADR-0013) the generator does not derive for a stage
a hub shares (`shared`, WP42), so WP73 refuses `SalesOrderHeader` for the three key columns and the stage stays inferred.
The hand view is the join: `SalesOrderHeader LEFT JOIN CurrencyRate ON CurrencyRateID`. Candidate: derive the
translation for the link's participation on a shared stage as for a link of its own (the hub's own key columns are
untouched), or split the link's stage from the hub's where a participation is translated. Release criterion 3 waits
for exactly this shape; a binding cannot express a join and should not.

## C29 — A role-qualified participation with no declared source column names an invented column (found by WP82)

Five of the eight stages WP82 had to alias needed it for one reason: a role-qualified participation whose model names
no `source_key_column` is staged under `<role>_<key>` (`SALES_PERSON_BUSINESSENTITYID`, `ORGANISATION_BUSINESSENTITYID`),
a column no relation carries, so the relation the offer or the evidence tier found is refused by WP73 and the stage
stays inferred (`stg_sales_person_sales_territory`, `stg_sales_person_territory_history`, `stg_business_entity_contact`,
`stg_store_sales_person`; WP90 declined the last for the same reason). The catalogue knows the column: the relation's
one foreign-key column resolving to that hub (two roles of one hub through one relation have two such columns, one
each — `BusinessEntityContact.BusinessEntityID` and `.PersonID`). Candidate: a rule that reads it as the participation's
source column where it is unambiguous, so the alias a human types today is derived; the alias field stays for the rest.

## C30 — A zero key for a hub whose key column is not integer or character (found by WP93, 2026-10-26)

WP93 binds `stg_sales_order` through a composite translation, and the link grew from 1 177 rows (every one of nine
participants present) to 13 976 (every order with a currency rate): the bound stage zero-keys its integer and
character participants (WP83), but the 17 489 orders without a currency rate stay outside `link_sales_order`, because
`hub_currency_rate`'s key holds a `timestamp` and WP83 §2.2 admits no zero key that cannot be cast into the column —
AutomateDV's `null_columns` writes `'-2'` into the stage column, WP86's row casts `'-1'` into the hub's. Two ways, both
a decision: hash a text form of the key column (the hub's own stage and every participation would derive
`CAST(col AS VARCHAR)` and hash that — the hash value is unchanged, the hub's key column becomes text), or treat an
optional participation as a link of its own (the owner's model has `link_sales_order_currency_rate` beside the order
link — a gate could say that a link with nine participants, three of them NULL in most rows, is the wrong unit of
work). The AutomateDV link macro drops every row whose foreign-key hash is NULL, so this is a rows question, not a
cosmetic one. Needs the owner's go.

## C31 — A table's own comment has no field in the house format (found by WP96, 2026-10-30)

The source catalogue states a description per table (AdventureWorks: 66 of 68, verbatim in the extract;
PostgreSQL `pg_description` with `objsubid = 0`, SQL Server's `MS_Description` on the table, Oracle's
`ALL_TAB_COMMENTS`), and `SourceTable` has no field for it — the derivation drops it (`derive.py`) and WP96's
reader reads it from no catalogue, because there is nowhere to put it. The modeler would read it where a
cryptic table name says nothing (the SAP case of C27 tier C in miniature). A field `comment` on `SourceTable`,
rendered where the column comments are rendered (the grounding prompt, the contracts), inert when absent, pinned
byte-identical for every existing input. Small; needs the owner's go, because it changes what an agent sees.

## C32 — A ratified model exported into TurboVault Engine's import schema (found by reading the competitor, 2026-10-30)

Scalefree's `turbovault-engine` (read 2026-10-30, `docs/competitive-landscape.md`, `docs/log.md` under that date)
takes a finished Data Vault metamodel and renders a dbt project on datavault4dbt. Since 2026-04-29 it embeds an MCP
server whose `commit_model` tool accepts a `ModelImportSchema` — hubs, links, satellites with their source mappings,
an optional free-text `reasoning` — and whose `generate_dbt` tool renders the project; its `export_model_json`
documents the full shape. Vault-Agent's ratified model (the ADR, the review queue's decisions, the bindings) has
everything that schema asks for, and more than it can hold (the evidence, the gates' verdicts). An exporter from
`DVModel` plus bindings into that schema — a file, or the MCP calls — would serve a datavault4dbt customer with
the modelling this project does and the generation theirs does, without a second generator in this repo. What it
is not: a second code-generation backend (ADR-0003 names AutomateDV; the owner's decision of 2026-10-04 keeps it the
one backend until it runs clean, and holds until he lifts it). What it needs before a line is written: a decision
whether exporting into a competitor's format is wanted at all, an ADR under ADR-0007's layer scope, and a pinned
fixture of the schema at the version read (0.21.0) — the schema is theirs and moves with their releases (their
issues #214 and #215 touch exactly `commit_model` and `validate_model`). Needs the owner's go.
