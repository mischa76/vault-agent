---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP98 — Profiling as a selectable list of deterministic checks, read from the source system (C27 stage 2)

Status: **Approved and in progress** (2026-10-30, the owner's go: „push beides, dann C27 stage 2") · Owner: Mischa
Eismann · Author: Claude. Backlog C27 stage 2 (`backlog-2026-10-candidates-3.md`, the owner's idea of 2026-10-24).
Builds on the profiling format (WP9 §3.2, `profiling.py`, `ColumnProfile`), the catalogue command (WP96, ADR-0017)
and ADR-0008 #4, which permits exactly this: „an explicitly invoked, read-only, scoped profiling step — never an
autonomous agent logging into production sources".

## 1 What is wrong, in one paragraph

The mapper's and the validator's profiling evidence is a file someone writes by hand (WP9 §3.2: „never produced by the
pipeline logging into a source"), and nothing in the repository produces it — the three profiling files that exist are
hand-authored or synthetic. A customer with a database and no profiling tool has no way to give the mapper the
statistics that turn a `llm_semantic` key pick into a `profiled_key` one, or the validator's optional-participant
warning into an error with evidence (WP94). Stage 1 (WP96) reads the catalogue and touches no row; the statistics
need rows, which is why ADR-0017 put stage 2 behind the residency note first.

## 2 The rules

1. **A command, not a capability of the pipeline.** `vault-agent profile --schema S [--table T …] --out profiling.yml
   [--check C …] [--sample N] [--examples K]`, the URL from `--url` or `VAULT_AGENT_SOURCE_URL` as for
   `source-schema`. The pipeline still reads profiling from a file only (`--profiling`); no agent, node or tool gains a
   database connection. The catalogue reader's protocol stays row-less (WP96's invariant): the profiler is a module of
   its own (`profiler.py`) over SQLAlchemy Core on a reflected table, and says in its first line that it reads rows.
2. **Scoped.** `--schema` is required; `--table` (repeatable, `Schema.Table` or a bare name in the named schemas)
   narrows to ADR-0008 #2's candidate set. Without `--schema` the command lists what the connection sees and exits 2;
   a schema or table the catalogue lacks exits 2; no URL exits 2; a missing driver or a refused connection exits 1
   with the password replaced, as in WP96.
3. **Counts always, the rest selectable.** Per table `row_count`; per column `null_ratio`, `distinct_count` and
   `uniqueness_ratio` = distinct ÷ non-null (0 when nothing is non-null) — the three the consumers read — are computed
   for every column, exact over all rows, by SQL aggregates (`count(*)`, `count(c)`, `count(distinct c)`). The
   selectable checks, `--check` repeatable, default `range lengths patterns`:
   - `range` — `min`/`max`, on numeric and temporal columns only (SQLAlchemy's reflected `Integer`, `Numeric`,
     `Float`, `Date`, `DateTime`, `Time`), rendered as text (`isoformat`, integers as they are, decimals without
     trailing zeros). **Never on a character column**: a character minimum is a row value (a name, an address).
   - `lengths` — `min_length`/`max_length` by `char_length`, on character columns (`String` and its subclasses).
   - `patterns` — the value **shapes** of a character column from a sample: every digit `9`, every letter `A`, every
     other character kept, cut at 32 characters; the five most frequent with their share of the sampled non-null
     values (`patterns: [{shape, share}]`).
   - `examples` — **off by default**: `--examples K` writes the first K distinct non-null sampled values of every
     column that has a range or a length (`example_values`, the field the consumers already read). The only check
     that writes a character column's values; the residency note says when not to.
   `--check none` means counts only. A column of any other type (binary, JSON, a type the dialect lacks) gets counts
   only.
4. **A sample is a sample and says so.** `patterns` and `examples` read the first `--sample` rows the database
   returns (default 10 000; no `ORDER BY`, because the data copy may have no key and a sort of a large table is not
   the operator's intent). The aggregates of rule 3 are never sampled. The file's header names the sample size.
5. **Nothing is written that was not measured.** One statement per table carries every aggregate; if the database
   refuses it (PostgreSQL has no equality operator for `xml` or `json`, so `count(distinct)` fails at planning), the
   profiler retries column by column and **omits** a column that still fails, naming it on stderr — never a zero in
   its place, because `uniqueness_ratio: 0.0` reads as evidence of a non-key. A statistic with no value (the minimum
   of an empty table) is absent, not null.
6. **The house format, grown but unchanged for its readers.** `ColumnProfile` gains `min`, `max`, `min_length`,
   `max_length` (`None` by default) and `patterns` (empty by default; `ValuePattern(shape, share)`); the loader takes
   them because the model does, and a file without them loads as before. The written file is the loader's shape —
   `tables: [{table, schema, row_count, columns: [{name, uniqueness_ratio, null_ratio, distinct_count, …}]}]` — with
   `table` the bare name as the catalogue spells it, `schema` and `row_count` as per-table keys the loader already
   ignores (documented in `load_profiling`). Determinism as WP96: tables by (schema, name), columns in ordinal order,
   ratios rounded to six places, a header with the hidden URL, the scope, the checks and the sample size, no
   timestamp. **The consumers are pinned byte-identical:** the mapper's payload and the validator's evidence read the
   four fields they read today; the new fields reach no model input. Showing a shape or a range to the mapper is a
   measured change (WP34 §3.8's rule) and a WP of its own.
7. **The mapper finds a profile the way the validator does.** `SourceMapperAgent` looks a profile up by exact
   `table`/`column` today; the validator normalises both through `normalize_identifier` (WP94). A catalogue and its
   data share one spelling at a customer, but the house's own data copy spells `salesorderid` where the declared
   schema says `SalesOrderID` — and the invariant says ask the helper. The mapper's lookup goes through one function
   in `profiling.py` (exact first, normalised second); inert on every existing fixture, where the spellings are equal.
8. **Residency, said where it is read.** A dated addendum to `deployment-residency.md` and to manual 10.7: the
   pipeline still reads no row; this command does, inside the customer's environment, and what leaves it in the file
   is counts, ratios, shapes and — with `range` — numeric and temporal extremes, which are row values (a salary
   maximum, a birth date minimum): a data-sensitive context runs `--check lengths patterns` or `--check none`, and
   never `--examples`. A dated note appended to ADR-0008 records that #4's explicitly invoked step now exists.

## 3 Not this WP

Candidate keys and inclusion dependencies (stage 3: an inference with its own class, ratified at the checkpoint; the
statistics here let a reader see `uniqueness_ratio: 1.0, null_ratio: 0.0`, and that reading stays the consumer's).
Showing the new fields to any model (rule 6). `row_count` or `schema` in `state.profiling` (the loader ignores them,
as it did). A profiling dataset for the AdventureWorks eval cases (the chain does not pass `--profiling`; a profile
of the data copy is an instrument here, not an input there). SAP (C27 tier C). The workbench. Requirements from the
catalogue (stage 4, with C1's ADR).

## 4 Pre-registration

- **P1** (keyless, SQLite, the statistics): a six-column miniature (integer, varchar, numeric, date, text, blob;
  five rows with nulls and repeats) profiles to the hand-computed values — row_count 5; the integer column
  uniqueness 1.0, null 0.0, `min`/`max` as text, no lengths; the varchar column non-null 4 of 5, distinct 3,
  uniqueness 0.75, null 0.2, lengths 4 and 10, two shapes `AA99999999` 0.75 and `AA-9` 0.25, no `min`/`max`; the
  numeric column `min` `3`, `max` `10.5`; the date column `min` `2019-12-31`; the blob column counts only; an empty
  table row_count 0, every ratio 0, no range, no lengths, no patterns; `examples` absent by default and the first two
  distinct sampled values on `--examples 2`; `--check none` leaves counts only. Red before the change (no module).
- **P2** (keyless, the ladder): an executor that refuses every statement naming one column → that column omitted,
  every other column present, one stderr line naming it. Red before.
- **P3** (keyless, the file and the loader): the written file loads through `load_profiling` with every value equal;
  two renders byte-identical; the header carries the hidden URL, the schemas, the checks and the sample size and no
  password; a file without the new keys loads with the defaults; the mapper's payload and the validator's issue list
  are byte-identical for a profile with and without the new fields; the mapper finds a profile keyed `salesorderid`
  for the declared column `SalesOrderID` (red before: the lookup is exact).
- **P4** (keyless, the command through Typer's runner): no URL exits 2; no schema lists the catalogue and exits 2; an
  unknown check exits 2; a table the schema lacks exits 2; the file is written from the environment URL on the
  SQLite fixture.
- **P5** (local PostgreSQL 16, by hand): the data copy in `vault` (transferred 2026-10-24; 68 tables, 601 columns,
  four types): `vault-agent profile` on its five schemas with the default checks, twice, byte-identical, 0 stderr
  lines; `row_count` equal to `count(*)` by psql on 68 of 68 tables; on `Sales.SalesOrderHeader` `salesorderid`
  uniqueness 1.0 and distinct 31 465, `currencyrateid` null_ratio 1 − 13 976 ÷ 31 465 (0.555824), `salesordernumber`
  one shape `AA99999` with share 1.0, `orderdate` a `min` and `max`; the file loads (68 tables); the password appears
  nowhere, the hidden URL once. Then `aw_ddl` rebuilt from the DDL instrument (empty tables, the seven `xml`
  columns): row_count 0 on 68 tables, no range and no lengths anywhere, and **exactly the seven `xml` columns
  omitted with seven stderr lines** — the ladder's live case.

## 5 Guards

`tests/test_wp98_profiling_from_source.py` (P1–P4), committed red before the change. P5 is run by hand and recorded
in `docs/log.md`. The residency addendum, the ADR-0008 note, manual 4.2/5/6.1/10.7, README and CHANGELOG go with the
change.
