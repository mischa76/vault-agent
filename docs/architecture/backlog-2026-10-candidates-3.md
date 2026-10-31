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

## C33 — Two translations in one stage whose natural keys share a column name (found by the C1 experiment's build, 2026-10-30)

A link staged through two or more surrogate→natural-key translations (WP36) projects each hub's natural key under
its own name; when two hubs are keyed alike — `Department.Name` and `Shift.Name`, the `Name` of every AdventureWorks
reference table once a hub is keyed on it — the view reads `r1.NAME as NAME, r2.NAME as NAME`, the schema.yml
declares the `not_null` test twice on one column, dbt refuses to parse, and had it built, the link would hash both
hubs from one column: wrong data. Found by the keyless PostgreSQL build of arm T's fifth project: 5 of its 42
translation views collide, all on `NAME`; arm A has no two such hubs in one link. WP89 already projects a key apart
from a *relation's own* homonym (`<KEY>_VIA_<THROUGH>`); the same rule between translations is the candidate — the
second and every later translation projecting a name an earlier one took gets `_VIA_<THROUGH>`, and the stage's
hash key follows, as WP89's does. Gate or guard: a stage must never project one column name twice.

## C34 — A carried satellite still reads the stage its hub had before it became multi-source (found by the same build)

`sat_unit_measure_details` (step 3, on the single-source `hub_unit_measure`) reads `stg_unit_measure`. Step 4 made
the hub multi-source (`ProductVendor` as a second feed) and still rendered the legacy feed's stage under its old
name beside `stg_unit_measure_productvendor`; step 5, carrying the hub, renamed the legacy feed's stage to
`stg_unit_measure_unitmeasure` — and the carried satellite kept `stg_unit_measure`, which no longer exists. dbt
refuses to parse the whole project on the missing node. Arm A's build went through with one hand view of that name
(`PASS=389` of 396). Candidate: a carried satellite without a `source_table` binds to its hub's legacy feed
through `satellite_feed` — the rule ADR-0011 states — on every step, not only on the one that materialised the feed;
and `project_self_contained` (or a keyless `dbt parse`, which WP78 can run) should see a `ref()` to a stage the
project does not render.

## C35 — A feed stage hashes a satellite payload column its own relation lacks (found by the same build)

`stg_unit_measure_productvendor`, the second feed of the multi-source `hub_unit_measure`, hashes `NAME` for
`sat_unit_measure_details`' hashdiff — `ProductVendor` has no `Name`; PostgreSQL refuses the view. The satellite
belongs to the legacy feed (ADR-0011: a satellite is bound to one feed); its hashdiff has no place in the other
feed's stage. WP73's gate refuses a *link* staging bound to a relation lacking a hashed column; the hub feed stage
has no such gate. Candidate: the gate for feed stages, and the generator rendering a satellite's hashdiff only
in the stage of the feed the satellite is bound to.

## C33 — closed by WP100 (2026-10-30)

The second and every later translation of a stage projecting a name an earlier one took is projected as
`<KEY>_VIA_<THROUGH>` at the moment the participation is staged (`wp100-translation-collision-spec.md`); arm T's
fifth project, regenerated keylessly, parses and builds, and the two pushed-apart links that built join every hub
row (`docs/log.md`, 2026-10-30). The same build found C36.

## C36 — A translation model's name exceeds the platform's identifier limit (found by WP100's build, 2026-10-30)

`translation_model_name` joins every translated relation into `stg_<link>_via_<a>_and_<b>…`; arm T's fifth
project names one view 74 and one 103 characters long, and PostgreSQL's identifiers end at 63 — dbt refuses the
relation (`Relation name … is longer than 63 characters`) and the stage reading it, its tests and its link are
skipped (`stg_culture_product_description_product_model_via_productmodel_and_culture`,
`stg_sales_order_customer_via_customer_and_creditcard_and_currencyrate_and_shipmethod_and_salesterritory`). The
platform profile (`rules/platforms.py`) carries no identifier length; Snowflake and Databricks allow 255, Fabric
128. The collision had hidden it: before WP100 the project did not parse. Candidate: an identifier limit per
platform in the profile, a translation name that stays under it — the link's name with a short deterministic
suffix when the joined list would exceed the limit; the list is already in the view's header and in
`key_translation` — and a render-time check of every generated relation name against the limit.

## C34 and C35 — closed by WP101 (2026-10-30)

The carried catalogue's `stage_bindings` names the grandfathered feed of a hub that is already multi-source in the
existing model, so its stage keeps `stg_<entity>` on every later step; an existing satellite without `source_table`
puts its payload into that feed's stage alone, the raw-vault generator names the same stage through the same
helper, and `project_self_contained` fails on a raw-vault model reading a stage the project does not render
(`wp101-legacy-feed-carried-spec.md`). Arm A's fifth project, regenerated keylessly, parses without the hand view and
builds to the two known inferred-stage errors (`docs/log.md`, 2026-10-30).

## C36 — closed by WP102 (2026-10-31)

The platform profile carries its identifier limit; a translation model's name that would exceed it becomes
`stg_<link>_via_<n>_<digest>`, and any other staging name over the limit is flagged
(`wp102-identifier-limit-spec.md`). Arm T's fifth project, regenerated keylessly, builds PASS=507 of 514 to the known
inferred stage and the data copy's type artefact (`docs/log.md`, 2026-10-31).

## C37 — The derived AdventureWorks schemas carry no nullability, so WP94's gate can only warn (found by WP102's build, 2026-10-31)

`link_sales_order_customer` in arm T's fifth project holds 13 976 rows of `SalesOrderHeader`'s 31 465: the 17 489
orders without a `CurrencyRateID` hash a NULL `CURRENCYRATE_HK` (the translated key is `CurrencyRateDate`, a
`datetime`, which no zero key can be cast into), and AutomateDV's link macro keeps only rows whose foreign-key
hashes are all non-NULL (`macros/tables/postgres/link.sql`, 0.11.4, lines 40–41). WP94's gate saw exactly this and
said so — `W_LINK_OPTIONAL_PARTICIPANT on link_sales_order_customer … reads SalesOrderHeader.CURRENCYRATEID — of
unknown nullability` — a warning with the own-link remedy, because the declared schema states no `nullable` and no
profile was given; the unattended chain does not act on a warning. The extract knows: `schema_extract.json`
carries `nullable` for all 471 columns (81 nullable), and `eval.adventureworks.derive` does not transcribe it,
although the house format has the field and the gate reads it. Candidate: emit `nullable` in `derive.py` (every
derived case changes its `source_schema.yml` — a deliberate re-derivation, the two case-name pins untouched), so the
gate becomes an error there and the remedy is applied; and, independently, the eval could treat a WP94 warning on a
link of three or more as a decision the harness answers with the remedy.

## C37 — closed by WP103 (2026-10-31)

The derivation transcribes the extract's `nullable` for every column (`wp103-derived-nullability-spec.md`); the six
derived cases and their five C1 copies re-derived, nothing else changed. Both chains' fifth step of 2026-10-30,
replayed keylessly through the validator, now get `E_LINK_OPTIONAL_PARTICIPANT` on the sales-order link with the
own-link remedy where they had the warning (`docs/log.md`, 2026-10-31). The second half of the candidate — the eval
answering a warning with the remedy — is not needed for these cases and stays open for catalogues that cannot say.

## C27 stage 4 — ADR-0019 proposed (2026-10-31)

Requirements from the catalogue: `adrs/ADR-0019-drafted-requirements.md` proposes a deterministic drafting command
in place of the stage's *LLM text marked as such*, on the C1 experiment's evidence. Stage 4 closes with the ADR's
acceptance and the WP that builds the command.

## C28 and C29 — closed by WP93 and WP95 (2026-10-26; noted here 2026-10-31)

Both were built and measured on 2026-10-26 and never annotated here: C28 by WP93 (composite-key translation — the
paid chain's last step builds with zero hand views, `wp93-composite-key-translation-spec.md`, `docs/log.md`
2026-10-26) and C29 by WP95 (a role's column from the relation's foreign key — the sign-off alias derived by rule,
`wp95-role-column-from-foreign-key-spec.md`, same date). The plan of 2026-10-30 listed both as open because this file
and the index row still did; found on 2026-10-31 by reading the log before starting on them. Open from WP93: the
two-hop composite case (unmeasured) and the owner's own build; from WP95: a catalogue without foreign keys.

## C32 — ADR-0020 proposed (2026-10-31)

The decision C32 asked for is drafted as ADR-0020 (`adrs/ADR-0020-turbovault-export.md`): no exporter now; when a
datavault4dbt customer asks, the round-trip project JSON, never the MCP proposal schema. Read at HEAD `2dd2d98`
(0.21.0): the engine has two import shapes, and the minimal one cannot hold a multi-source hub, a role, a key
translation or a binding's alias. The mapping into the full shape is in the ADR; nothing installed or run.

## C38 — A role link's stage is offered a feed of the hub instead of the relation that carries the role column (found by the twenty-third chain's build, 2026-10-31)

The twenty-third chain's fifth project (`20261031T032606335763Z`) builds PASS=417 of 421 on PostgreSQL; the two
errors are `stg_product_size_unit_measure` and `stg_product_weight_unit_measure` — the stages of
`link_product_size_unit_measure` and `…_weight_…` (`hub_product` + `hub_unit_measure` in the roles `size` and
`weight`, `source_key_column` `SizeUnitMeasureCode` / `WeightUnitMeasureCode`). The offer bound both to
`ProductVendor`, the second feed of `hub_unit_measure`, which carries `UnitMeasureCode` but neither role column; WP73
refused correctly (`binding_rejected: ProductVendor: 2`) and the stages read the `inferred` placeholder. The relation
that carries both hashed columns and the declared foreign key to `UnitMeasure` is `Product` — in the catalogue,
unoffered. Candidate: the offer for a link stage prefers the relation that carries every hashed column (the FK
evidence of WP90 already names it for the role participation) over a feed of a participating hub. New in this chain:
the twenty-second built no product→unit-measure role links.

## C39 — `stage_refs_inferred` counts only `SOURCE_BINDING`, so a refused binding's stage is not counted (same build)

`eval/run.py` sets `stage_refs_inferred` to the number of `SOURCE_BINDING` flags; a stage whose binding WP73 refused
(`BINDING_REJECTED`) reads the same `inferred` block and fails the same way, but the metric said 0 for a project with
two. Candidate: count both kinds (the generator's own comment in `sources.yml` already names both), so the eval's
number is the build's.

## C38 and C39 — closed by WP105 (2026-10-31), and C38's mechanism corrected

C38 as written above places the offer in step 5; the kept outputs place it in **step 4**: step 3 had bound both stages
to `Product` by WP90's evidence tier (two `link_binding_evidence` decisions, reason `key`) and carried the binding;
step 4's resolution over the increment alone found `ProductVendor` the one offer, WP95's rule derived the missing
role column from its foreign key, and this run's override preceded the carried binding (WP77 §3) — step 4's project
read the product's size and weight units from the vendor relation (built 2026-10-31: 265 link rows each, 0 of 460
stage rows agreeing with `Product`), silently green. Step 5 refused the carried `ProductVendor` only because the
harness carries no `stage_aliases` (C40) and the carried catalogue has no foreign keys (C41). WP105 makes a carried
binding the first tier of the link's relation resolution at every call site, and `stage_refs_inferred` counts refused
stages (C39). Spec `backlog-2026-07/wp105-carried-binding-tier-spec.md`; measured keyless: the chain's fifth project
PASS=421 of 421, the two links holding all 504 products with the real units on 176 / 205 of them.

## C40 — The eval harness carries `stage_bindings` but not `stage_aliases` between steps (found by WP105, 2026-10-31)

`eval/run.py` loads `carried_bindings` for the next step and for a resumed step, never `carried_aliases`; `cli.py`
(`run --existing`) and `ui/runs.py` load both (WP82). An alias a human typed or WP95 derived in one step therefore
reaches the next step in the CLI and the workbench but not in a measured chain, where WP73 then refuses the carried
relation for the very column the alias supplied — the twenty-third chain's step 5 (`binding_rejected: ProductVendor`
×2) was that, on a binding that happened to be wrong. Two lines; the harness should load what the product loads.
Needs the owner's go because it changes what the chains measure.

## C41 — The carried catalogue declares no keys (found by WP105, 2026-10-31)

`dump_source_catalogue` writes a table's columns (with types and nullability) and nothing else: no primary key, no
unique keys, no foreign keys. A relation read from the carried catalogue can therefore not be judged by WP95's role
derivation, WP85's grain gate or the evidence tier's key clause — the twenty-third chain's step 5 could not derive
`SIZE_UNITMEASURECODE` on the carried `ProductVendor` where step 4 could. The source schema reader (WP96) and the
derivation (WP85) carry all three; the catalogue should carry them unchanged, byte-identical where a table declares
none. Small; needs the owner's go because every brownfield step's catalogue changes shape.
