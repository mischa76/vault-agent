---
type: spec
status: not-measured
updated: 2026-10-18
---

# WP79 — A source column named like a reserved word is escaped and aliased in the stage, per target platform, so the same project builds on PostgreSQL, Snowflake and Databricks

Status: **Approved and in progress** (2026-10-18, the owner's go for WP79) · Owner: Mischa Eismann
· Author: Claude. From the twenty-first chain's PostgreSQL build (`docs/log.md`, 2026-10-18): six
staging views failed with `syntax error at or near "group"` / `"primary"` — `SalesTerritory.Group`,
`ProductProductPhoto.Primary` — on a project that had built on Databricks. No prompt change; the
suite stays keyless.

## 1 The defect, in one paragraph

AutomateDV's `stage` macro selects the relation's columns and the hashed and derived references
**unquoted**, and so do the generated raw-vault models for their payload. `GROUP` and `PRIMARY`
are reserved words in PostgreSQL (101 of them: `pg_get_keywords()`, categories R and T, read from
the installed server) and in Snowflake, not in Databricks — so a column name that is ordinary
data in AdventureWorks makes a view unparseable on two of the four target platforms, and no gate,
flag or test saw it: the stage hashes `TERRITORYID` only, the column arrived through
`include_source_columns`. AutomateDV has the mechanism already: a derived column with `escape:
true` puts its `source_column` into `columns_to_escape`, and `print_list` then escapes that column
wherever it appears, in the relation's own spelling (`"group"` on PostgreSQL). What it needs is to
be told, and the downstream references need a name that is not reserved.

## 2 The rules

1. **The list is read from the platform, frozen in `rules/`.** `RESERVED_COLUMN_WORDS` holds
   PostgreSQL's reserved keywords (R and T categories, 101 words, `pg_get_keywords()` on
   PostgreSQL 16.15 — the strictest of the target platforms; Snowflake's list is contained in
   it). `is_reserved_column(name)` normalises and looks up; `stage_column_name(name)` is the
   column downstream code uses: the normalised identifier, with a trailing underscore
   (`GROUP_`, `PRIMARY_`) when reserved. The code generator's `_to_column` is this function, so
   payload, key and date references of hubs, links and satellites name the alias.
2. **The physical spelling is the platform's.** `PlatformProfile.identifier_fold` —
   `lower` for PostgreSQL, `upper` for Snowflake, `none` for Databricks and Fabric (case-
   insensitive) — and `physical_name(column)` give the spelling an escaped reference must use:
   `"group"` on PostgreSQL, `"GROUP"` on Snowflake, either on Databricks.
3. **The stage declares the escape at render time.** `render_stage_model` and the staging
   metadata rewrite nothing in the spec: for every reserved column the spec references (hashed,
   derived source, pass-through) they add a derived column `<ALIAS>: {source_column:
   <physical>, escape: true}`, rewrite hashed references to the alias (AutomateDV hashes after
   deriving), and turn a derived column whose source is reserved into the mapping form with
   the physical spelling and `escape: true`. The relation's own column stays in the view,
   escaped by AutomateDV. Projects without reserved columns render byte-identically.
4. **The gates follow.** WP73's `E_STAGE_COLUMN_NOT_IN_SOURCE` reads a derived column's
   source from the mapping form too; the alias is a derived name and therefore available.

## 3 Guards before the change

1. `is_reserved_column` over `Group`, `group`, `PRIMARY`, `Order` → true; `Name`, `Size`,
   `ProductID` → false; `stage_column_name("Group") == "GROUP_"`,
   `stage_column_name("ProductID") == "PRODUCTID"`; `RESERVED_COLUMN_WORDS` has 101 entries
   and contains `GROUP`, `PRIMARY`, `ORDER`, `USER`.
2. `platform_profile("postgres").physical_name("Group") == "group"`, databricks `"Group"`.
3. `build_staging` on a `SalesTerritory` fixture (hub on `TerritoryID`, a satellite with
   `Name`, `Group`): the stage declares `GROUP_` with `source_column: 'group'` and `escape:
   true` for PostgreSQL (`'Group'` for Databricks), the hashdiff lists `GROUP_` and never bare
   `GROUP`; the metadata carries the mapping form; the validator's WP73 gate raises nothing.
4. The code generator: `sat_sales_territory_details` has `GROUP_` in its payload and no bare
   `GROUP`; a hub keyed on `Order` has `src_nk` `ORDER_` and its stage hashes `ORDER_` from an
   escaped derived `ORDER_`.
5. The bank fixtures (no reserved words) render byte-identically — the existing baselines.

## 4 Pre-registration

The twenty-first chain's fifth project regenerated keylessly from its kept model and catalogue
(the WP77 bindings as its overrides) for PostgreSQL and rebuilt on the local server: the six
reserved-word failures are gone; the build fails on exactly the eight inferred stages and their
dependants — **PASS=324 of 340** expected (340 − 8 − 8 dependants), `hub_sales_territory` and the
`SalesTerritory` satellites built with their `Group` values, `link_product_product_photo` with
`Primary`. The same regeneration for Databricks is parse-identical in shape (not run: the quota).

## 5 Not in this WP

Reserved words as *table* names (dbt quotes relations already); a per-platform reserved list
narrower than PostgreSQL's (the union is the safe choice, and an unnecessary alias costs a
suffix, not a build); a flag telling the reviewer about the alias (the stage's SQL and the
metadata show it; a review item would be noise).

## 6 Results

*(appended after the change)*
