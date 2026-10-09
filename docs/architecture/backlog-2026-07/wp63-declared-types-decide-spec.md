---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP63 — The declared column type decides a contract field's type; the model fills only gaps

Status: **Approved and in progress** (2026-10-09, within the owner's standing mandate to reduce
review load deterministically; found on the thirteenth chain) · Owner: Mischa Eismann · Author:
Claude. Touches the data-contract agent and `rules/`. A product rule (the code owns a declared
fact), not steering.

## 1 Problem, measured

Thirteenth chain, `20261009T205307885768Z`, step 1 (first under the 5.5 defaults): 15
`undetermined_type` decisions — `BusinessEntityAddress.BusinessEntityID`, `…AddressID`,
`Person.EmailPromotion`, … — every one a column whose **declared source schema carries its SQL
type** (`int`, `datetime`, `nvarchar(50)`; `eval/adventureworks/derive.py` transcribes the type
verbatim). The contract agent hands the model the column **names only** (`_assets`) and asks it
for a `data_type`, „'unknown' if it genuinely cannot be determined — never guess“. Sonnet 4.6
guessed from the names (0–3 unknowns per chain); Sonnet 5.5 takes the instruction literally and
answers `unknown` for what it was not told. Both are wrong in kind: a declared type is a fact
the code holds, and asking a model for it is the guess.

## 2 The rule

**A contract field's type is the declared column type where one is declared; the model's answer
counts only where none is.** `rules.json_type_for_sql(declared) -> str | None` maps the SQL
Server base types (the family this corpus declares) to JSON Schema types: `int`, `bigint`,
`smallint`, `tinyint` → `integer`; `bit` → `boolean`; `decimal`, `numeric`, `money`,
`smallmoney`, `float`, `real` → `number`; `char`, `nchar`, `varchar`, `nvarchar`, `text`,
`ntext`, `uniqueidentifier`, `xml`, `date`, `time`, `datetime`, `datetime2`, `smalldatetime`,
`datetimeoffset`, `binary`, `varbinary`, `image`, `hierarchyid`, `geography`, `geometry` →
`string`; a length or precision suffix is ignored; anything else (a user-defined type such as
AdventureWorks' `Name`, `Flag`, `Phone`) → `None`. In `_build_contract`: declared type mapped →
that; else the model's `data_type`; else `unknown`, and only then the `undetermined_type` flag.
The model still describes, exemplifies and annotates every field as before.

## 3 Guards before the change

1. `json_type_for_sql`: `int` → `integer`, `nvarchar(50)` → `string`, `money` → `number`, `bit` →
   `boolean`, `Name` → `None`, `""` → `None`.
2. A contract built against a declared schema with typed columns and an enrichment that answers
   `unknown` for them carries the mapped types and raises no `undetermined_type` flag; an
   untyped (bare-name) column with the model's `integer` carries `integer`; an untyped column
   the model calls `unknown` is flagged as today; a user-defined type with the model's answer
   carries the answer.

## 4 Pre-registration

On the next chain: `undetermined_type` decisions only for columns without a declared base type
(AdventureWorks: the user-defined types the model does not resolve) — ≤ 5 per chain on 5.5,
against 15 in step 1 alone on the thirteenth.

## 5 Not in this WP

Passing the declared types to the model as context (it no longer needs them for the type;
descriptions may still benefit — a separate, measurable prompt change); dialects beyond SQL
Server's base types.

## 6 Results

*(appended after the change)*

**2026-10-09 — built, keyless.** Guards `d4ef00a` (failing on import), change `c04607f` (a mypy
cast in the commit carrying this line). `rules.json_type_for_sql`, the declared-type precedence
in `_build_contract`. Guards 1–2 pass; full suite, ruff, mypy. §4 is **not yet measured live** —
the thirteenth chain runs on the code before this change; the fourteenth measures it.

**2026-10-09 — fourteenth live chain** (`20261009T213238859667Z`): **7 `undetermined_type` decisions** (the
thirteenth: 68), every one a user-defined type (`Flag`, `NameStyle`) or a computed column — the
map's boundary as §2 draws it; §4 predicted ≤ 5, missed by two on exactly that boundary. Chain
decisions 84, the lowest recorded on any model.

**2026-10-10 — WP64** resolves the alias types in the derivation, so the map now covers every
AdventureWorks column but the computed ones (`AS`); the seven remaining `undetermined_type`
decisions of the fourteenth chain fall to one or none on the next.
