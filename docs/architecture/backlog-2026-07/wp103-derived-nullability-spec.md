---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP103 — The derived AdventureWorks schemas carry the extract's nullability (C37)

Status: **Approved and in progress** (2026-10-31, the owner's word: C37 before the C1 ADR) · Owner: Mischa Eismann ·
Author: Claude. Found by WP102's keyless PostgreSQL build of arm T's fifth project (`docs/log.md`, 2026-10-31).

## 1 What is wrong, in one paragraph

`link_sales_order_customer` in arm T's fifth project holds 13 976 of `SalesOrderHeader`'s 31 465 rows: the orders
without a `CurrencyRateID` hash a NULL `CURRENCYRATE_HK` — the translated key is `CurrencyRateDate`, a `datetime`,
which no zero key can be cast into — and AutomateDV's link macro keeps only rows whose foreign-key hashes are all
non-NULL (`macros/tables/postgres/link.sql`, 0.11.4, lines 40–41). WP94's gate saw exactly this and said so, as
`W_LINK_OPTIONAL_PARTICIPANT` with the own-link remedy — a warning, because the declared schema states no
`nullable` and no profile was given; the unattended chain does not act on a warning. The extract knows:
`schema_extract.json` carries `nullable` for all 465 columns of the five business schemas (77 nullable), the house
format has had the field since WP94 (`SourceColumn.nullable`, written by WP98's reader), the gate reads it — and
`eval.adventureworks.derive` does not transcribe it. Both chains of 2026-10-30 got the warning on their fifth step.

## 2 The rules

1. **The derivation transcribes nullability.** Every column entry `build_source_schema` writes carries
   `nullable: true|false` from the extract, after `type` and before `comment` — the order WP98's reader writes
   (`source_schema_reader._entry`), so a derived file and a file read from a source are one shape. Transcribed,
   never curated (WP30 §2.3): the extract's value, nothing decided here. The extract's value is faithful on the one
   axis a column DDL leaves open — a column of an alias type (`Name`, `Flag`, …) without its own `NULL`/`NOT NULL`
   inherits the type's; checked against `user_defined_types`, no column is declared nullable whose alias type is
   `NOT NULL`.
2. **Every derived case is re-derived, and the C1 copies with it.** The six `source_schema.yml` under
   `eval/datasets/adventureworks_*` (the five areas and `adventureworks_full`) change by exactly one key per column;
   the `adventureworks_drafted_*` cases are byte-identical copies of the authored ones (their `dataset.yml` says so)
   and are copied again. `golden_mapping.yml`, the requirements and the two case-name pins are untouched; the demo's
   frozen inputs (`demo/workbench-adventureworks/…/inputs/*_source_schema.yml`, the inputs of a recorded run) are not
   re-derived — they already differ from the eval files and must keep reproducing their run.
3. **Nothing else changes.** No gate, no generator, no prompt. WP94's gate becomes an error on these cases by its
   own rule 1 (evidence of NULLs → `E_LINK_OPTIONAL_PARTICIPANT`, refuses, feeds the re-model loop); that the
   modeler then applies the remedy is WP94's claim, measured there on the replayed demo step, and is not re-measured
   here — it needs a live step.

## 3 Not this WP

The second half of C37 — the eval answering a WP94 *warning* on a link of three or more with the remedy — is not
needed once the cases carry nullability, and a customer's catalogue read by `vault-agent source-schema` carries it
too; it stays a candidate for catalogues that cannot say. A zero key for non-character key columns (C30's other
way). Nullability for the synthetic cases (`bank`, `messy_insurance`, `scale_*`): nobody declared it there.

## 4 Acceptance (keyless)

`tests/test_wp103_derived_nullability.py`, committed red: the derivation states the extract's `nullable` for all
465 columns (77 nullable) in the house format's key order; every shipped case declares it, the drafted copies
match byte for byte, the combined case counts the same 77; WP94's miniature (its hubs and three-way link) over the
shipped Sales case gets the error with the own-link remedy, not the warning, and never names the customer's integer
participation. The rest of the suite unchanged — `test_derivation_is_deterministic` keeps pinning the re-derived
files.

## 5 Pre-registration (keyless)

- **P1** The re-derivation changes the six `source_schema.yml` and their five drafted copies and nothing else: no
  golden, no requirements, no other file in the tree.
- **P2** Both chains' fifth step of 2026-10-30 (arm A `20261030T184653194084Z`, arm T `20261030T184653223619Z`),
  replayed through the validator from their kept `dv_model.yml` with the re-derived Sales schema: the one
  `W_LINK_OPTIONAL_PARTICIPANT` becomes `E_LINK_OPTIONAL_PARTICIPANT` on the same link
  (`link_customer_sales_order`, `link_sales_order_customer`) with the same remedy
  (`link_sales_order_currency_rate`), and every other issue code and count is unchanged.
- **P3** `uv run pytest` green, no fixture updated.

Measured before this registration, on the local data copy (PostgreSQL 16, the five business schemas, 465 columns),
and recorded as evidence rather than prediction: of the 77 columns the extract declares nullable, 46 hold NULLs in
the copy and 31 none; of the 388 declared `NOT NULL`, 386 hold none and 2 hold some (`Production.Document.FileExtension`
4 of 12 rows, `Production.Document.DocumentNode` 1 of 12 — the copy carries no `NOT NULL` constraints and these two
are an artefact of its load, not of the extract); `SalesOrderHeader.CurrencyRateID` is NULL in 17 489 of 31 465
rows, the rows the link lost.

Not predicted: the number of other links in the kept chains the error would name (the replay counts them).
