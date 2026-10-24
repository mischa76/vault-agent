---
type: spec
status: not-measured
updated: 2026-10-24
---

# WP82 — Bindings at sign-off: a stage's relation and its column aliases ratified in CLI and workbench alike; `--map`, profiling and the platform through the API; a guard holding the CLI's options against the API's models (C4, C18 second half)

Status: **Approved and in progress** (2026-10-24, the owner's go to the recommendation „C18's second half together with
C4/WP82") · Owner: Mischa Eismann · Author: Claude. Backlog C4 (`backlog-2026-10-candidates.md`, WP82 reserved) and
C18 (`backlog-2026-10-candidates-2.md`); WP90 closed C18's first half (the evidence tier) and left this half on the
record. Release criterion 3 (`release-1.0-criteria.md`): „AdventureWorks builds without a hand-made view: every link
stage bound by rule or at sign-off".

## 1 What is wrong, in one paragraph

A stage no rule binds reads an inferred `raw_<base>` that does not exist, and the only remedy is a hand-made view in
the warehouse. The owner's build needed seven (three since WP90); the paid chain's last step
(`demo/workbench-adventureworks/…/20261022T234439976097Z`) needed ten, and **regenerated with today's generator still
needs eight** (measured 2026-10-24, keyless: 191 stages, 8 inferred). Six of the eight are *refused* bindings (WP73):
the rule found the relation — `Product`'s subcategory and model, `BusinessEntityContact`, `SalesPerson`,
`SalesTerritoryHistory`, `SalesOrderHeader` — but the stage names a column the relation does not carry
(`SALES_PERSON_BUSINESSENTITYID` for `BusinessEntityID`, `ORGANISATION_BUSINESSENTITYID` for `BusinessEntityID`,
`PRODUCTID` on the subcategory table). Every hand view says what the human knows: *this relation, and this column
under that name* — `SELECT businessentityid AS storeid, salespersonid AS sales_person_businessentityid FROM Store`. The
CLI and the workbench cannot be told that: `resume --map` binds a hub's key through a mapping proposal, link stages
bind only from proposals and offers (`link_source_overrides`), and the workbench's checkpoint cannot even send `--map`.
The CLI also takes `--profiling` and `--target-platform` at start and `--map`/`--mappings` at the checkpoint, none of
which the API's `StartRun`/`Decision` models carry; nothing holds the two option sets together, so the next CLI option
bypasses the workbench silently (C4, the owner's word of 2026-10-20: identical results from both).

## 2 The rules

1. **A `bindings` decision at sign-off.** `{stage: {"relation": R, "columns": {STAGE_COLUMN: relation_column, …}}}`
   — the stage as the review item names it (`stg_store_sales_person`), the relation as declared (increment or
   carried catalogue), the aliases optional. CLI: `resume --bind "STAGE=RELATION"` and
   `--bind "STAGE=RELATION(STAGE_COLUMN=column, …)"`, repeatable, a decision flag like the others; the interactive
   checkpoint asks for each inferred or refused stage and hands the answer to the same parser. API:
   `Decision.bindings`. Workbench: a relation field and an aliases field on every `source_binding` and
   `binding_rejected` item; the checkpoint payload carries, per inferred stage, what the human needs to fill them
   (the stage's expected columns, the relation the rule tried and why it was refused). The run's CLI equivalent
   records every `--bind`.
2. **Checked before anything runs** (`check_stage_bindings(state, bindings) -> list[str]`, one helper for every
   path): the stage exists among this run's stages; the relation is declared; every alias names a column of the
   relation; after the aliases the relation carries every column the stage hashes or derives — WP73's rule, the same
   helper staging applies (`missing_stage_columns`). An error names the stage, the relation and the missing columns.
   The CLI prints it and exits 1 before resuming; the API answers 400; the prompt asks again. `apply_human_decision`
   skips an invalid entry with a warning — defence in depth, never the first line.
3. **Application.** `VaultAgentState.ratified_bindings` (new, empty by default: byte-identity). `source_overrides`
   applies them **last** — a human's decision overwrites the name rule, the offer, the evidence tier and a ratified
   proposal alike, for hub stages and link stages. `build_staging` adds each alias as a derived column
   (`relation_column AS STAGE_COLUMN`, WP41's own mechanism for a role's column) before `bind_sources`, so the WP73
   check sees it and the hash reads it; a null group keeps the relation column, as WP41's aliases do. The stage's
   metadata says `source_binding: declared` and records the aliases under `ratified_columns`; the re-bind replaces
   the stage's `source_binding`/`binding_rejected` flags, as it does today. A ratified binding is a decision, not a
   proposal: it has no `accept` of its own and is applied whether or not the human accepts.
4. **It travels.** `stage_bindings` carries the relation to the next increment (WP77, unchanged); a new catalogue
   block `stage_aliases` carries the aliases; `load_carried_aliases` → `state.carried_aliases` → `build_staging`
   applies them together with the carried binding, before the WP73 check — without this, the next step would refuse
   the carried relation for the very column the alias supplied. Pre-WP82 catalogues load as today (no block, no
   aliases).
5. **`--map` through the API.** `Decision.mappings` (`{concept: "TABLE.COLUMN"}`, the `--map` payload) and
   `Decision.mapping_sources` (the multi-source answers an edited `mappings.review.yml` carries); the workbench offers
   a `TABLE.COLUMN` field on every `mapping_unresolved` item. Multi-source keys stay listed under *unresolved* in the
   workbench as today and are answered through the API or the CLI's file — said in the UI, not hidden.
6. **The start options through the API.** `StartRun.profiling` (a project file of kind `profiling`, loaded by the
   CLI's `load_profiling`) and `StartRun.target_platform` (the CLI's choices); `run.json` records both; the equivalent
   says `--profiling` and `--target-platform`; the workbench's start form gets both selectors. The default platform is
   the CLI's default.
7. **The guard.** `tests/test_wp82_parity.py` enumerates the click parameters of `run` and `resume` and holds each
   against an explicit table — the API field it maps to, or a named exception: `--out`, `--write`, `--trace`,
   `--interactive` belong to the process, not to the decision; `--mappings` and `--resolutions` are files whose
   content is the `mappings`/`mapping_sources`/`resolutions` dicts. A CLI option without a row fails the test, in both
   directions (an API field without a CLI option fails too).
8. **Roles do not move.** `(source_binding, none)` stays a disclosure; the fields are offered where the item is shown
   (disclosures unfolded), and on the `binding_rejected`/`ambiguous` decisions. The decision count a chain is judged
   by (WP34 §6, WP53) is unchanged by this WP.

## 3 Acceptance (keyless)

`tests/test_wp82_bindings_at_sign_off.py`: the parser (plain, with aliases, malformed); `check_stage_bindings`
(unknown stage, undeclared relation, alias to a missing column, a missing hashed column after aliases, a valid one);
`apply_human_decision` binding a link stage with an alias (the stage bound, the alias derived, the flag gone, the
override winning over an offer) and a hub stage; the aliases in the staging metadata and the catalogue, loaded back
and applied by the next increment; `_has_decision_flags`; the interactive prompt producing the same payload as the
flag (WP12's parity rule); the API: `POST …/checkpoint` with `bindings` binding the stage and recording `--bind`, a
wrong relation answered 400, `mappings` recorded as `--map`; `StartRun` with profiling and platform recorded in
`run.json` and the equivalent. `tests/test_wp82_parity.py` as in §2.7. Frontend (`Review.test.tsx`, `Project.test`):
the relation and alias fields render on a `binding_rejected` item and reach `onDecide` as `bindings`; the mapping
field on `mapping_unresolved`; the platform and profiling selectors reach `startRun`. The rest of the suite unchanged.

## 4 Pre-registration

Measured keyless on `vault-dev` (PostgreSQL 16, the `vault` database's AdventureWorks schemas), the paid chain's last
step regenerated with today's generator from its stored state (`.vault-agent/state.json`, the demo's run
`20261022T234439976097Z`):

- **P1** Baseline, measured before this spec (2026-10-24): 191 stages, **8 inferred** — six refused by WP73
  (`stg_product_subcategory` → `ProductSubcategory`, `stg_product_model` → `ProductModel`, `stg_sales_order` →
  `SalesOrderHeader`, `stg_business_entity_contact` → `BusinessEntityContact`, `stg_sales_person_sales_territory` →
  `SalesPerson`, `stg_sales_person_territory_history` → `SalesTerritoryHistory`), one `none`
  (`stg_work_order_operation`), one `ambiguous` (`stg_store_sales_person`). With these seven bindings, each saying
  what the demo's hand view (`inferred_views.sql`) reads: `stg_work_order_operation=WorkOrderRouting`,
  `stg_product_model=Product`, `stg_product_subcategory=Product`,
  `stg_business_entity_contact=BusinessEntityContact(ORGANISATION_BUSINESSENTITYID=BusinessEntityID,
  CONTACT_PERSON_BUSINESSENTITYID=PersonID)`, `stg_sales_person_sales_territory=SalesPerson(
  SALES_PERSON_BUSINESSENTITYID=BusinessEntityID)`, `stg_sales_person_territory_history=SalesTerritoryHistory(
  SALES_PERSON_BUSINESSENTITYID=BusinessEntityID)`, `stg_store_sales_person=Store(STOREID=BusinessEntityID,
  SALES_PERSON_BUSINESSENTITYID=SalesPersonID)` — **7 of 8 bind; `stg_sales_order` stays inferred**: its hand view
  joins `CurrencyRate` through `CurrencyRateID`, a translation, not a binding (§5).
- **P2** Two builds into two fresh schemas: the baseline project with its eight hand views, and the bound project with
  **one** view (`raw_sales_order`). Both PASS for every node; both idempotent on a second build (every incremental
  model `INSERT 0 0`). The constructs the seven stages feed — `hub_work_order_operation`, `hub_product_model`,
  `link_product_model`, `hub_product_subcategory`, `link_product_subcategory`, `link_business_entity_contact`,
  `link_sales_person_sales_territory`, `link_sales_person_territory_history`, `link_store_sales_person` and their
  satellites — hold **equal row counts** in both schemas, or more in the bound schema by exactly the rows whose
  participant key is NULL (a declared stage gets WP83's zero key, an inferred view did not; WP90 saw 17 against 14 on
  `link_business_entity_sales_territory`) — each such difference listed with its count.
- **P3** The API path, keyless: a stub run paused at sign-off, `POST …/checkpoint` with a binding → the stage bound,
  `--bind` in the equivalents; a relation lacking a hashed column → 400 naming the column.
- **P4** The next increment, keyless: a project whose stage was bound with an alias, read by `run --existing`, binds
  that stage again from the catalogue, alias included — no `binding_rejected`.
- **P5** The owner's three remaining hand views, by reading (their run state is not on this machine, so not rebuilt):
  `raw_work_order_product_location` = `WorkOrderRouting` plain, `raw_business_entity_store_sales_person` =
  `Store(STOREID=BusinessEntityID, SALES_PERSON_BUSINESSENTITYID=SalesPersonID)` — both expressible by the field;
  `raw_sales_order_currency_rate` is the same join as `stg_sales_order`.

Not predicted: whether AutomateDV applies `null_columns: optional` to a derived alias (the build says; if not, the
alias's null group is dropped and the record says so); wall time.

## 5 Not this WP

The join shape (`stg_sales_order`, the owner's `raw_sales_order_currency_rate`): a hub-and-link stage whose
participation key lives a join away is a translation (WP36) the generator does not derive for a stage a hub shares —
recorded as backlog C28, the one hand view criterion 3 still waits for. The role-column naming itself (a role-qualified
participation with no declared source column reads an invented `<role>_<key>` instead of the relation's one foreign-key
column resolving to its hub — the reason five of the eight needed an alias at all): a rule change, backlog C29. The
offer tier counting a participant's primary-key column (C18's other idea): no remaining stage needs it. A build from
the workbench (the owner's word: the workbench ends at the written project). A workbench field for multi-source keys.
