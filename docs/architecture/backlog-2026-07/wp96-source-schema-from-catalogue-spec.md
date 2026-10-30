---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP96 — The declared source schema read from the source system's catalogue: `vault-agent source-schema` (C27, stage 1)

Status: **Approved and in progress** (2026-10-30, the owner's go for C27; the reader technique is ADR-0017's
recommendation, proposed, the owner's decision pending) · Owner: Mischa Eismann · Author: Claude. Backlog C27 stage
1 (`backlog-2026-10-candidates-3.md`, the owner's idea of 2026-10-24). Builds on the house format (`SourceTable`,
WP9 §3.1, WP34 §3.1, WP85, WP94) and its loader (`source_schema.py`); the cross-check is the DDL extract
(`eval/adventureworks/extract.py`, WP30).

## 1 What is wrong, in one paragraph

A run's declared source schema is a file someone writes. For AdventureWorks it was parsed out of Microsoft's install
script by a regex instrument that took four corrections to read every constraint (2026-09-12, WP85); a customer has no
install script, only a database, and the alternative — typing 465 columns, 90 foreign keys and 440 comments by hand —
is not one. Everything the file carries is in the database's catalogue already: names, types, nullability, keys,
foreign keys, comments. A command reads them into the house file; the loader, the grounding, the proposer and the
gates see what they see today.

## 2 The rules

1. **Transcription, never interpretation.** The reader writes what the catalogue says: every table of the named
   schemas (views only on `--views`), every column in ordinal order, the type as the vendor's dialect spells it
   (lowercased), `nullable` always, the comment when the catalogue has one (verbatim, whitespace kept), the primary
   key, every unique constraint and every unique index that is not the primary key and not the constraint's own
   index, every foreign key with its referenced schema (the dialect's default schema when the catalogue omits it),
   the table's schema and the connection's database. No key is inferred, no GUID is excluded, no name is
   normalised — the `rowguid` unique indexes the derivation drops by design are in the file, because they are in the
   catalogue.
2. **Deterministic.** Two reads of one catalogue give one byte-identical file: tables sorted by (schema, name),
   columns in ordinal order, keys sorted by their column lists, foreign keys sorted by (columns, referenced table).
   The file's header names the connection with the password hidden and the schemas read; it carries no timestamp.
3. **The house format, through the house loader.** The file is what `load_source_schemas` reads: `source_schemas:`
   with `table`, `schema`, `database`, `columns` (`name`, `type`, `nullable`, `comment`), `primary_key`,
   `unique_keys`, `foreign_keys`. Empty lists are omitted, as the derivation omits them. An entry that the loader
   would refuse is a defect of the reader, pinned.
4. **One seam.** `read_source_schema(reader, schemas=…, database=…)` takes a `CatalogueReader` protocol with the
   seven methods ADR-0017 names; `inspector_reader(url)` is the SQLAlchemy implementation. A dialect that cannot
   say something raises `NotImplementedError` and the reader records nothing for it (no comments on SQLite); a type
   the dialect does not know is written as an empty `type`, named on stderr, never guessed.
5. **The command.** `vault-agent source-schema --schema S [--schema T …] --out FILE [--views]` with the URL from
   `--url` or `VAULT_AGENT_SOURCE_URL` (a password belongs in the environment, not the shell history). Without a
   schema it lists the catalogue's schemas and exits 2; without a URL, exit 2; a missing driver or a refused
   connection exits 1 with the dialect's message and the password hidden. The command reads no row: no `SELECT`
   on a user table, pinned by the protocol's surface.
6. **Residency.** Stage 1 is metadata; what leaves the machine afterwards is what leaves it today (the file is the
   model's input). Said in the manual's data boundary (10.7), not in a new residency record.

## 3 Not this WP

Profiling (C27 stage 2: touches data, needs consent and sampling in `deployment-residency.md` first), key
inference (stage 3), requirements from the catalogue (stage 4, with C1's ADR). A table comment (no field in
`SourceTable`; the derivation drops it too — recorded as candidate C31). Identity and computed columns as such
(transcribed as ordinary columns; the house format has no field). The SAP dictionary reader (tier C). SQL Server
and Oracle measured (tier A waits for the source-system VM, `home-server-eigenbau`). The workbench (C4's parity
guard covers `run` and `resume`; a catalogue step in the workbench is a later increment under ADR-0015). A loader
for AdventureWorks data (C23) — the DDL instrument of §5 is its schema half, not its data.

## 4 Pre-registration

- **P1** (keyless, SQLite with an attached schema): a miniature with two tables, a composite primary key, a
  unique constraint, a unique index, a composite foreign key, a nullable and a not-null column, a view — the reader
  returns both tables in order, the columns in ordinal order with `nullable`, the keys, the foreign key with the
  referenced schema filled, the view only on `--views`; the written file loads through `load_source_schemas` to the
  same list; two writes are byte-identical; comments arrive through a stub reader that has them and are absent
  where the reader raises `NotImplementedError`; an unknown type is `""`. Red before the change (no module).
- **P2** (keyless, the CLI): no `--schema` → exit 2 and the schema names on stdout; no URL → exit 2; a URL whose
  driver is not installed → exit 1, the message names the driver and never the password. Red before.
- **P3** (keyless, the instrument): `eval/adventureworks/postgres_ddl.py` renders the extract as PostgreSQL DDL —
  68 tables, 465 columns, 68 primary keys, 55 unique indexes, 90 foreign keys, 66 table comments, 440 column
  comments, counted on the statements; the ten computed columns (`AS` in the extract) are declared `text`; the six
  alias types resolve to their base types. Red before.
- **P4** (local PostgreSQL 16, the measurement): the DDL applied to a fresh database `aw_ddl`; the command run on
  its five schemas; against `eval/datasets/adventureworks_full/source_schema.yml` and the extract: 68 tables,
  every column name in order equal (465), `nullable` equal to the extract's for every column, `primary_key` equal
  for 68 tables, `foreign_keys` equal as sets (90, with `references_schema`), `unique_keys` equal to the extract's
  55 alternate keys — of which the 26 `rowguid` keys are absent from the derived file by its design, present here
  by rule 1 — column comments equal for 440 columns, no comment on the other 25; the type pairs
  (SQL Server spelling → PostgreSQL spelling as compiled) form a function with the ten `AS` columns at `text`.
  The output loads through `load_source_schemas`.
- **P5** (local PostgreSQL, the as-transferred copy in `vault`): the command on the five schemas of the copy made
  on 2026-10-24 returns 68 tables with lowercase column names, every column nullable, no key, no foreign key, no
  comment — recorded as what a data copy loses, not as a target.

## 5 Guards and instrument

`tests/test_wp96_source_schema_from_catalogue.py` (P1, P2, P3), committed red before the change together with the
`catalogue` extra (SQLAlchemy, which the SQLite fixture needs). The instrument `eval/adventureworks/postgres_ddl.py`
is checked in with the change; P4 and P5 are run by hand and recorded in `docs/log.md`.
