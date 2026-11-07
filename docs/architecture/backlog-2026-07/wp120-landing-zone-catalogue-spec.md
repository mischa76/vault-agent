---
type: spec
status: measured
updated: 2026-11-07
---

# WP120 — A catalogue read from the landing zone: PostgreSQL's type spellings and the technical columns (C47 stage 1, C48)

Status: **Approved and in progress** (2026-11-07, on the owner's go to build both small stages before the live chain
on a PostgreSQL catalogue) · Owner: Mischa Eismann · Author: Claude. Candidates C47 (stage 1) and C48
(`backlog-2026-11-candidates.md`).

## 1 What is wrong

Every chain so far ran on `derive.py`'s transcription of Microsoft's DDL. A catalogue read by `source-schema` (WP96)
or the workbench (WP119) from the PostgreSQL copy differs in two ways nothing has measured:

1. **The types are PostgreSQL's spellings** (`integer`, `varchar(n)`, `timestamp without time zone`,
   `numeric(19, 4)`, `uuid`). `json_type_for_sql` (WP63) knows SQL Server's names only: `integer`, `boolean`,
   `uuid`, `timestamp…`, `double precision` answer `None`, and the contract agent asks the model for a type the
   declaration holds. `null_safe_type` reads `character varying(n)` as `character`, unknown.
2. **The landing tables carry the load columns** the loader adds (`load_datetime`, `record_source`, WP110). They
   are transcribed as ordinary columns. `unread_payload` then lists them as payload no satellite reads, the error
   gate `E_HUB_PAYLOAD_UNREAD` (WP54) asks the re-model loop for a satellite that reads them, and a satellite whose
   hashdiff holds `load_datetime` writes a new row for every key on every batch — wrong data, invisible on a
   re-run of the same batch (reproduced keylessly on 2026-11-07: `['ModifiedDate', 'load_datetime',
   'record_source']`). WP96 measured against `aw_ddl`, a DDL-only database without them.

## 2 The rules

1. **PostgreSQL's spellings in the type rules.** `_SQL_JSON_TYPES` gains `integer`, the serials, `boolean`/`bool`,
   `double precision`, `character varying`, `character`, `bpchar`, `timestamp` with and without time zone, `time`
   with and without time zone, `interval`, `uuid`, `bytea`, `json`, `jsonb`, `citext`; the lookup reads the base
   before a parenthesis case-insensitively, as it did. `NULL_SAFE_TYPES` gains `character` and `bpchar` (the first
   word of `character varying(n)` / `character(n)`). Every SQL Server answer stays as it was (pinned).
2. **Technical columns are not source columns.** `VaultAgentState` drops from `source_schemas` and
   `carried_schemas` every column whose name equals, case-insensitively, one of the naming profile's
   `load_datetime`, `record_source`, `applied_dts` — the columns the pipeline adds itself — unless the column is
   part of the table's declared primary or unique key (then it is a business column that happens to share the name,
   and it stays). What was dropped is recorded per `Schema.Table` in `technical_source_columns`, so a run says it.
   The file on disk stays a transcription (WP96's rule 1); the drop happens where the model's inputs are formed.
   Idempotent: a state read back from its checkpoint drops nothing more.
3. The profile decides: a project with `load_datetime: LDTS` drops `LDTS`, not `load_datetime`.

## 3 Not this WP

C47's family field and its ADR. `infer-keys` and `profile` still read every column of the source (they are
commands against the database, not the model's inputs). The report does not yet print `technical_source_columns`.

## 4 Acceptance and pre-registration (keyless)

`tests/test_wp120_landing_zone_catalogue.py`, committed red: T1 the PostgreSQL spellings' JSON types, the SQL Server
table pinned; T2 the zero-key sets; T3 the drop, its record, the profile's names, a key column kept, idempotence;
T4 the payload gate's list without the load columns (the reproduction); T5 a schema without them untouched.
**P1** T1–T5 green, the whole suite green with no key reachable, ruff, bare mypy. **P2** every older guard
unchanged — the AdventureWorks files carry no technical columns, so every chain fixture's state is unchanged.
**Not measured here:** a live chain on the PostgreSQL catalogue — that is the run this WP prepares.

## 5 Measured

Appended after the run.

## 5 Measured (2026-11-07, keyless)

- **P1 ✔.** T1–T5: 30 guards green (19 of them red at `6870f5d`, the other 11 the spellings both tables already
  shared and the SQL Server table pinned). Whole suite with no key reachable: 1650 passed, 5 skipped (1620 before,
  plus these 30); ruff, bare mypy clean.
- **P2 ✔.** No older guard changed or failed: the AdventureWorks files and every fixture carry no column named like
  the profile's technical columns, so their states are what they were.
- **Not measured:** the live chain on the PostgreSQL catalogue, which this WP prepares; the report does not print
  `technical_source_columns` yet (§3).
