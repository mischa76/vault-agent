---
type: spec
status: not-measured
updated: 2026-10-10
---

# WP64 — AdventureWorks' alias types are resolved to their base types in the schema derivation

Status: **Approved and in progress** (2026-10-10, user: „ok, go, bau WP64“) · Owner: Mischa
Eismann · Author: Claude. Touches `eval/adventureworks/extract.py`, `derive.py`, the checked-in
extract and the derived `source_schema.yml` files. Transcription, not interpretation (WP30 §2.3):
the alias definitions stand in the same install script.

## 1 Problem, measured

Fourteenth chain (`docs/log.md` 2026-10-09): 7 `undetermined_type` decisions, every one a column
declared with one of AdventureWorks' six **SQL Server alias types** — `CREATE TYPE [Name] FROM
nvarchar(50) NULL`, `[Flag] FROM bit NOT NULL`, `[NameStyle] FROM bit NOT NULL`, `[AccountNumber]
FROM nvarchar(15) NULL`, `[OrderNumber] FROM nvarchar(25) NULL`, `[Phone] FROM nvarchar(25) NULL`
(`instawdb.sql`, lines 331–336, read 2026-10-10). The extractor transcribes every column's type as
written, so those columns carry the alias name; WP63's base-type map leaves an alias to the
model, rightly, because the name alone says nothing — and Sonnet 5.5 answers `unknown`. The
definition the name needs is in the same script the extractor already reads. Alias types are no
modelling-language construct; they are the database's (PostgreSQL domains and DB2 distinct types
are the same idea), and a derivation from a catalogue should resolve them before the schema
reaches an agent.

## 2 The rule

1. `extract.py` parses `CREATE TYPE [X] FROM <base>[(n)] [NOT] NULL;` into
   `extract["user_defined_types"]`: `{name: {"base_type": "nvarchar(50)", "nullable": true}}`,
   sorted by name; the column's `type` in the extract stays the alias (the extract transcribes).
2. `derive.py` resolves a column whose type (with or without a `dbo.` prefix) names a
   user-defined type to its `base_type` in `source_schema.yml`; every other type and every
   comment is byte-identical to before. No alias note in the comment: comments stay verbatim
   (WP30 §2.3), the alias is in the extract.
3. The checked-in extract is regenerated from the upstream script; its `tables` must be
   byte-identical to the current extract (the script has not changed), the new key the only
   difference. The five derived schemas change only in the columns that carried an alias.

## 3 Guards before the change

1. `parse`/`build_extract` on a snippet with the six `CREATE TYPE` lines yields the six
   definitions with their base types and nullability.
2. `build_source_schema` on an extract declaring `Name → nvarchar(50)` emits `type:
   nvarchar(50)` for a `Name` column and for a `dbo.Name` column, leaves `smallint` alone, and
   leaves the comment unchanged.
3. The checked-in extract carries exactly the six types; no derived `source_schema.yml` carries
   an alias type any more (the person schema's `NameStyle`, the purchasing schema's `Flag`).

## 4 Pre-registration

On the next chain: `undetermined_type` decisions 0 or near 0 on AdventureWorks (the fourteenth:
7 — six alias columns and one computed column, `PurchaseOrderHeader.TotalDue`, which the script
declares `AS` and the extractor records as such; that one stays the model's).

## 5 Not in this WP

Catalogue-driven resolution for live sources (`sys.types`, PostgreSQL domains) — the derivation
here reads a script; the principle is the same and belongs to a source-catalogue connector.

## 6 Results

*(appended after the change)*
