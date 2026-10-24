---
type: spec
status: not-measured
updated: 2026-10-22
---

# WP83 — Zero keys for nullable link participants: a link keeps the row whose participant is missing, and its satellites stop orphaning (C12, phase 1)

Status: **Approved and in progress** (2026-10-22, the owner's order of work: then C16 and C15, then as far as it goes alone — after the priority order I proposed, data defects next and C12 first) · Owner:
Mischa Eismann · Author: Claude. Backlog C12 (`backlog-2026-10-candidates-2.md`); found in the owner's
build of AdventureWorks (`docs/log.md`, 2026-10-22, steps 6 and 8). WP81 was a dropped sketch, WP82 is
reserved for CLI/workbench parity (C4).

## 1 What is wrong, in one paragraph

AutomateDV's `link` loads a row only when every participant's hash key is non-NULL, and a single-column
hash of NULL is NULL. A source row whose foreign key is empty therefore never reaches the link — while a
satellite on that link, hashing the link key over the same columns, keeps the row (a multi-column hash is
NULL only when every component is). Measured: `link_customer_business_entity` keeps 635 of 19 820
customers (each has a person *or* a store); `link_product_assembly_component` 2 387 of 2 484 triples and
`sat_product_assembly_component_details` holds 103 rows on 97 link keys no link row carries. Data Vault 2.0
answers this with **zero keys**: a missing optional participant is replaced by a fixed value before
hashing, so the relationship row exists and points at „unknown". AutomateDV 0.11.4 implements exactly
that in its stage — `null_columns: {required: […], optional: […]}` keeps the original as `<COL>_ORIGINAL`
and replaces NULL with `var('null_key_required', '-1')` / `var('null_key_optional', '-2')`
(`macros/staging/null_columns.sql`; the PostgreSQL dispatch uses `COALESCE`, the default `IFNULL`,
SQL Server `ISNULL`); the null CTE runs after derived columns and before hashing (`macros/staging/stage.sql`).
The generator passes no `null_columns`.

## 2 The rules

1. **Every stage that hashes a link key declares that link's participant columns as `optional`
   null columns** — the link's own stage and a link satellite's dedicated stage alike, so both hash the
   same value and the satellite cannot orphan. „Participant columns" are the stage columns each
   participation's hash is taken over (the role-qualified column, an alias's canonical column, a
   composite hub's column list).
2. **Only where the replacement is type-safe.** `COALESCE(col, '-2')` fails for a date, a boolean or a
   UUID. A participation qualifies when every relation column it reads has a declared type of the
   integer or character class (`int`, `bigint`, `smallint`, `tinyint`, `integer`, `char`, `nchar`,
   `varchar`, `nvarchar`, `text`, `string`, with or without length). Unknown type, another class, an
   inferred (unbound) stage, a translated participation (the key arrives through a join view): **no null
   handling** — today's behaviour, unchanged.
3. **`optional`, never `required`.** The catalogue does not say which foreign keys are mandatory; for a
   non-NULL value the replacement is a no-op, so every hash that exists today stays byte-identical —
   an existing vault is extended, never re-keyed.
4. **Output.** The rendered stage gains a `null_columns:` block and passes
   `null_columns=metadata_dict['null_columns']`; the staging metadata gains `null_columns`. A stage with
   no qualifying participation renders byte-identically to today.
5. **Not in this phase: zero-key rows in the hubs.** A link row with a zero key points at a hub key
   (`hash('-2')`) no hub row carries. DV2.0 puts `-1`/`-2` records into every hub; AutomateDV has ghost
   records for satellites only, and a typed zero-key feed per hub needs the hub key's type — phase 2,
   specified separately. Until then a join from such a link to its hub is an outer join.

## 3 Acceptance (keyless)

- A link whose participants are integer columns of a typed relation renders `null_columns` with every
  participant column under `optional`, and its metadata says so (`tests/test_wp83_zero_keys.py`).
- A link satellite's dedicated stage declares the same columns.
- A participation reading a `datetime` column, an untyped relation, an inferred stage: no `null_columns`.
- A composite participation qualifies only when all its columns do.
- A role-qualified participation (`assembly`/`component`) lists the role columns.
- The rest of the suite unchanged except fixtures that pin a link stage over a typed relation — updated
  in the same commit, with the reason.

## 4 Pre-registration (keyless `dbt build` on PostgreSQL, before the change is built)

The owner's Sales run (`demo/workbench-adventureworks/…/20261022T151530662480Z`) regenerated from its
`state.json` with the new generator, built whole into a fresh schema `aw_wp83` against the same
AdventureWorks tables, with `inferred_views.sql` re-pointed at that schema:

- **P1** `link_customer_business_entity` **19 820** rows (was 635).
- **P2** `link_product_assembly_component` **2 484** (was 2 387); `sat_product_assembly_component_details`
  has **0** rows whose link key the link lacks (was 103).
- **P3** `link_sales_order_sales_person` **31 465** (was 3 806), `link_sales_order_credit_card` **31 465**
  (was 30 334).
- **P4** `link_sales_order_currency_rate` **13 976**, unchanged: its stage is inferred (rule 2).
- **P5** every hub's row count equals the owner's `aw` build; every link without a NULL participant in its
  source equals it too.
- **P6** PASS for every model that passed in the owner's build (334 nodes), nothing new failing.

Not predicted: wall time.
