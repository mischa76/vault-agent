---
type: spec
status: not-measured
updated: 2026-10-04
---

# WP45 — Composite business keys, typed from the modeler to the hash

Status: **Approved and in progress** (2026-10-04, user: „Ok, leg los" on the analysis of the two
Sales failures; this is the second of the two) · Owner: Mischa Eismann · Author: Claude. Touches
`Hub`, `rules.canonical_hub_key_column` and its callers, the staging generator, the hub renderer,
`E_SAT_KEY_NOT_IN_SOURCE`, `W_BK_NOT_IN_SOURCE`, `E_HUB_HK_COLLISION`, the modeler's tool schema,
the FK-links Postgres demo. No steering-registry line; one backstop with telemetry (WP16).

## 1 Problem, measured

Step 5 (sales) of the chain `20260917T181755061438Z` is red on `E_SAT_KEY_NOT_IN_SOURCE` ×3. The
parents are keyed on composite keys the modeler wrote as one string: `hub_order_line` on
`SalesOrderID + SalesOrderDetailID` (the table's declared primary key is exactly these two) and
`hub_currency_rate` on `CurrencyRateDate + FromCurrencyCode + ToCurrencyCode` (the natural key;
the table also has a surrogate `CurrencyRateID`). Nothing types or parses that string:
`canonical_hub_key_column` normalises it into one identifier
(`SALESORDERID_SALESORDERDETAILID`) that no relation declares, the stage would hash a column that
is not there, and the gate refuses — correctly. The key-license pairing skips composite foreign
keys for the same reason (`ForeignKey.is_single_column`; 1 skip on this chain).

The warehouse side is not the obstacle. In the installed AutomateDV 0.11.4
(`demo/*/dbt_packages/automate_dv`): `macros/staging/hash_columns.sql` hashes a **list** of
columns under one key when the value is not a mapping (`columns[col] is not mapping` →
`automate_dv.hash(columns=<list>)`), and `macros/tables/postgres/hub.sql` takes `src_nk` through
`expand_column_list`, so a list is a legal natural key. The project's own link hash keys already
go through that list branch (`StagingSpec.hashed` holds `str | list[str] | _HashDiff`).

Composite keys are the rule, not the exception, in the landscapes this product is for
(`MANDT + KUNNR`, contract + version, policy + sequence). A modeller that cannot hash one is not
a DV2.0 modeller.

## 2 The rule

**A hub names the source columns its key hashes from; the hash is taken over all of them.**

1. **Typed, at the source.** `Hub.business_key_columns: list[str]` (default empty). Two or more
   entries make the key composite; `business_key` stays the business label. The modeler's tool
   schema exposes the field with that description; the prompt's field list names it.
   `rules.hub_key_columns(hub) -> list[str]` is the one helper (CLAUDE.md: „ask the helper in
   `rules/`"): the normalised columns when composite, else `[canonical_hub_key_column(hub)]`.
2. **Staging hashes the list.** A composite hub's stage: `HUB_HK: [COL1, COL2, …]` and every
   column passed through; a satellite on it hashes the parent key the same way from its own
   relation; a link participation of a composite hub hashes the participation over the list
   and the link's hash key over all participations' columns; a link satellite likewise.
3. **The hub's natural key is the list.** `_render_hub` sets `src_nk = ["COL1", "COL2"]`
   (the YAML metadata carries the list); single-column hubs render byte-identically.
4. **Gates read the list.** `E_SAT_KEY_NOT_IN_SOURCE` demands every column of the parent's key
   in the satellite's relation and names the missing ones; `W_BK_NOT_IN_SOURCE` checks each
   column of a composite key and names the missing ones instead of the label;
   `E_HUB_HK_COLLISION` compares key *tuples*, so a composite and a single key on one entity
   still collide.
5. **What this WP refuses rather than guesses** — new gate `E_HUB_COMPOSITE_UNSUPPORTED`: a
   composite hub that is multi-source (`HubSource` carries one column per feed), or that takes
   part in a link with a role, an alias (`source_key_column`) or a translation. Each of these
   needs a per-column mechanism that does not exist yet; staging them from the first column
   would be the silent wrong-data defect this project has had once (WP24). The gate feeds the
   re-model loop with the shape named.
6. **A backstop for the modeler's own notation.** `composite_key_split` (modeler, after the
   items are validated): a hub with no `business_key_columns` whose `business_key` splits on
   ` + ` into two or more parts that are **all declared columns of the hub's own relation**
   (the declared table whose name matches `source_entity`) gets those parts as its columns; the
   label is kept. Fires only with a declared schema and only when every part is grounded — a
   format repair, like `decoded_field` (2026-09-17), not an interpretation. One `backstop` trace
   event per hub, `backstop_id="composite_key_split"`. Gate behind it: `E_SAT_KEY_NOT_IN_SOURCE`
   / `W_BK_NOT_IN_SOURCE`, which refuse what the backstop did not repair.

Callers of `canonical_hub_key_column` that pair a *single* declared column with a hub
(`link_proposal`, `subtype_feed`, `E_LINK_KEY_WRONG_COLUMN`) keep calling it; for a composite
hub it returns the normalised label, which matches no column, which is the right answer — a
single-column foreign key cannot reference a composite key.

## 3 Guards before the change

Committed first, failing; then the change:

1. `hub_key_columns` returns the single canonical column for today's hubs and the normalised
   list for a composite one; the tool schema exposes `business_key_columns`.
2. Staging: a composite hub's stage hashes `HUB_HK` over both columns and passes both through;
   its satellite's own stage does the same; a link with a composite participant hashes the
   participation over the list and the link key over every column.
3. The hub renderer emits the list `src_nk`, and a single-key hub's SQL is unchanged (the
   staging and greenfield baselines hold).
4. `E_SAT_KEY_NOT_IN_SOURCE` is silent when the satellite's relation carries both columns and
   fires naming the one missing; `W_BK_NOT_IN_SOURCE` names the missing column of a composite
   key and is silent when all are declared; `E_HUB_COMPOSITE_UNSUPPORTED` fires for the
   multi-source and the role shapes and is silent for a plain composite hub.
5. The backstop splits `A + B` when both are declared on the hub's relation, emits one event,
   and does nothing without a schema, with an undeclared part, or when columns are already set.
6. The FK-links demo builder produces a composite hub (`hub_currency_rate`), its satellite and a
   link in which it takes part, and the dbt project builds on local PostgreSQL (§4, keyless).

## 4 Pre-registration

**Postgres (keyless, this WP's own evidence).** `demo/fk_links_postgres` gains `Currency` and
`CurrencyRate` seeds (3 rates over 2 currencies), `hub_currency` (`CurrencyCode`),
`hub_currency_rate` on (`CurrencyRateDate`, `FromCurrencyCode`, `ToCurrencyCode`),
`sat_currency_rate_detail` (`AverageRate`, `EndOfDayRate`) from `CurrencyRate`, and
`link_currency_rate_currencies` connecting the rate hub with `hub_currency` twice, as `from` and
`to`, each read from its own column — **the role participations are the single-key hub, the
composite hub takes part unqualified**, which is what §2.5 allows. Predicted: `dbt build
--full-refresh` green from an empty schema; the 3 rate rows hash to 3 distinct hub keys; all 3
satellite rows and all 3 link rows join `hub_currency_rate`; the link's `from`/`to` join
`hub_currency`; a second `dbt build` inserts 0 rows.

**The next live chain**, if the modeler keys the two hubs as on 2026-09-17:
- **P1.** The backstop fires twice in step 5 (`hub_order_line`, `hub_currency_rate`; every part
  is declared) — or zero times if the modeler fills `business_key_columns` itself now that the
  field exists; either way the two hubs are composite in the model.
- **P2.** `E_SAT_KEY_NOT_IN_SOURCE` 3 → 0 and `W_BK_NOT_IN_SOURCE` 2 → 0 in step 5. With WP44
  holding `E_HUB_HK_COLLISION` at 0, **step 5's gate is green for the first time** — unless a
  class not seen on 2026-09-17 appears, which the run will name.
- **P3.** The composite-key license skip stays 1 (`SalesOrderDetail`'s key into the order line is
  still not paired — pairing composite foreign keys is §5).
- **P4.** Nothing else moves; steps 1–4 are byte-identical in the keys they stage.

## 5 Not in this WP, and what it costs

- **Composite foreign keys in the proposer** (`is_single_column` skips them): pairing n columns
  with a composite hub's n columns in declared order. Small once this WP exists; it needs a
  case with a declared composite FK to be measured on.
- **Composite + role / alias / translation / multi-source**: refused by the new gate. Each is a
  per-column generalisation of an existing mechanism (`role_bk_column`, `derived` aliases,
  translation views projecting several columns, `HubSource` with a column list). The role shape
  is the likeliest to come first (`CurrencyRate` as from/to between two *composite* hubs would
  be one).
- **Dependent child keys as the alternative modelling** (order line as a link order–product with
  `SalesOrderDetailID` as CDK): the model already supports it on satellites; whether the modeler
  should prefer it is a steering question, left to the ledger.

## 6 Results

*(appended after the change, the Postgres build, and the next live chain)*

**2026-10-04 — built keyless and on PostgreSQL.** Commits `2541f05` (guards, failing) and
`7b6dd0f` (the change and the demo). Guards 1–6 of §3 pass; ruff, mypy, pytest 1090 passed. The
Postgres half of §4 held exactly: `PASS=113 WARN=0 ERROR=0` from an empty `fk_links_demo` schema
(was 103 before the four constructs); `hub_currency_rate` 3 rows, 3 distinct `CURRENCYRATE_HK`;
3 of 3 `sat_currency_rate_detail` rows and 3 of 3 `link_currency_rate_currencies` rows join the
rate hub; the link's `from`/`to` join `hub_currency` as seeded (CHF→EUR twice, EUR→CHF once); a
second `dbt build` leaves 3/3/3 rows. One fixture updated deliberately: the greenfield manifest's
`metadata/dv_model.yml`, which now carries the empty `business_key_columns` on every hub. The
validator has 33 `E_` codes (was 32); README updated. P1–P4 of §4 (the chain) are **not yet
measured live**.

