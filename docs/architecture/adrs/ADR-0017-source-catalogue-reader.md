# ADR-0017: Reading the source catalogue from the source system — one reflection library, or catalogue queries per vendor

**Status:** Proposed (draft by Claude, 2026-10-30, on the owner's go for C27 — the decision is the owner's; WP96 is built on the recommendation and swaps behind one seam if he decides otherwise)
**Date:** 2026-10-30
**Decision makers:** Mischa Eismann

## Context

The three inputs of a run are files someone writes: the requirements, the declared source schema
(`--source-schema`), the profiling. For AdventureWorks the schema was parsed out of Microsoft's install
script (`eval/adventureworks/extract.py`), which a customer does not have; a customer has a database. Backlog
C27 (`backlog-2026-10-candidates-3.md`, the owner's idea of 2026-10-24) asks for the schema to be read from
that database, in four stages of rising risk. Stage 1 is metadata only: tables, columns with types and
nullability, primary and unique keys, declared foreign keys, column comments — into the house
`source_schemas:` file the loader already validates (`source_schema.py`, `state.SourceTable`). Nothing in
stage 1 reads a row. The question this ADR answers is *how* the catalogue is read.

What the reader must deliver, from the house format's consumers: the column names and order (grounding,
staging), the type spelling (contracts, the translation's casts, the gates' type families through
`rules._type_base`, which lowercases and takes the first word), nullability (WP94's gate), the primary key
and unique keys (`E_SAT_GRAIN_NOT_UNIQUE`), the foreign keys with their referenced schema (the proposer, the
translations), the column comments verbatim (the mapper's evidence). Transcription, never interpretation —
the same discipline the DDL extractor keeps.

What the target market brings: PostgreSQL and SQL Server first (the demo line and the sample's home), Oracle
and DB2 at banks, SAP HANA and SAP ERP/S/4 at insurers and industry, Snowflake, Databricks and BigQuery as
modern sources. SAP's catalogue is not the database's: it lives in the ABAP Dictionary (`DD02L`, `DD03L`,
`DD08L`/`DD05S`, texts in `DD02T`/`DD04T`), and its foreign keys are dictionary relationships, not
constraints — no database reflection reaches them.

## Decision (proposed)

**Option A — SQLAlchemy's `Inspector`, behind a small reader protocol of our own.** One reader for every
dialect SQLAlchemy or a third party ships: `get_table_names`, `get_columns` (name, type, nullable,
comment), `get_pk_constraint`, `get_unique_constraints`, `get_indexes` (the unique ones), `get_foreign_keys`
(constrained columns, referred schema, table and columns), `get_table_comment` — read from the installed
package, `sqlalchemy/engine/reflection.py` 2.1.6, the typed shapes in `engine/interfaces.py`
(`ReflectedColumn`, `ReflectedForeignKeyConstraint`, `ReflectedUniqueConstraint`, `ReflectedIndex`). The
type is spelled as the vendor's dialect compiles it (`TypeEngine.compile(dialect=…)`), lowercased, so
`rules._type_base` reads the same families it reads today. Comments come from the dialect where it has
them: PostgreSQL from `pg_description` (`dialects/postgresql/base.py` 4486, 4840), SQL Server from the
`MS_Description` extended property (`dialects/mssql/base.py` 3787, 4787), Oracle from `ALL_COL_COMMENTS`;
a dialect without them raises `NotImplementedError`, which the reader treats as „no comments", not as a
failure (`reflection.py` 1338). The reader takes the inspector through a protocol with exactly those
methods, so the keyless tests run on SQLite (the standard library's driver; schemas by `ATTACH`) and a
reader that is not a database reflection at all — SAP's dictionary, tier C — implements the same protocol
later. The library is an optional extra (`catalogue`), the vendor driver is the operator's install
(`psycopg2` is already in `demo`; `pyodbc`/`pymssql`, `oracledb`, `ibm_db_sa`, `sqlalchemy-hana`,
`snowflake-sqlalchemy`, `databricks-sqlalchemy`, `sqlalchemy-bigquery` are documented, not shipped).

## Alternatives considered

- **Option A — SQLAlchemy `Inspector`** (recommended). *For:* one code path, verified against the
  installed package rather than nine vendors' documentation; keyless tests on SQLite without a server;
  the dialects for every platform the stack already names exist and are maintained by their vendors
  (Snowflake, Databricks, BigQuery, HANA ship their own); comments, unique indexes and composite foreign
  keys are reflected, which is exactly the evidence the gates and the proposer need. *Against:* a new
  dependency in the core package's extras (2.1.6, pure Python, no driver of its own); a vendor's reflection
  quirk is the library's to fix (PostgreSQL omits the referred schema when it is the default one — the
  reader fills it from `default_schema_name`); the vendor's type spelling comes out as the dialect
  compiles it, not as the catalogue stores it (`timestamp without time zone`, not `timestamp`) — harmless
  to `_type_base`, visible in the file.
- **Option B — catalogue queries per vendor, by hand.** `information_schema` for PostgreSQL and SQL
  Server (plus `sys.extended_properties` for the comments), Oracle's `ALL_TABLES`/`ALL_TAB_COLUMNS`/
  `ALL_CONSTRAINTS`/`ALL_COL_COMMENTS`, DB2's `SYSCAT.*`, HANA's `SYS.*`. *For:* no dependency; every
  query readable in full; the SAP dictionary is just one more set of queries. *Against:* nine readers to
  write and keep right, each verifiable only against a running system of its vendor — tiers B and C
  would stay „written from documentation" far longer; the composite-key, unique-index and comment paths
  are exactly where vendors differ most; the keyless tests would need a fake per vendor.
- **Option C — both: the `Inspector` where a dialect exists, a hand-written reader where it does not.**
  This is Option A with the protocol taken seriously: SAP's dictionary reader (tier C) is a
  hand-written reader behind the same protocol, and nothing else is written by hand until a vendor's
  reflection is measurably wrong. Recorded here so the SAP package has its place; not a separate choice.

## Consequences

- **Positive.** A customer's database becomes an input without anyone transcribing DDL. The
  AdventureWorks cross-check is a real PostgreSQL catalogue (WP96 P4), so the reader's transcription is
  measured, not asserted. The protocol keeps the reader testable keylessly and keeps SAP open.
- **Negative.** The optional extra and the operator's driver install are two steps the manual must say
  (4, 6.1). Verification tiers stay as C27 lists them: A measured on PostgreSQL now, SQL Server and Oracle
  when the source-system VM exists; B written and marked unverified; C a package of its own.
- **Neutral.** The house format gains nothing in this ADR — a table comment has no field in
  `SourceTable` (the derivation drops it too); that is a candidate, not a consequence. Stages 2–4 of C27
  (profiling, key inference, requirements from the catalogue) keep their own ADR with C1; stage 2 touches
  data and belongs in `deployment-residency.md` before it is built.

## References

- Backlog C27 — `docs/architecture/backlog-2026-10-candidates-3.md`.
- The house format — `src/vault_agent/state.py` (`SourceTable`, `SourceColumn`, `ForeignKeyRef`),
  `src/vault_agent/source_schema.py`; the DDL extractor — `eval/adventureworks/extract.py`.
- SQLAlchemy 2.1.6 as installed — `engine/reflection.py`, `engine/interfaces.py`,
  `dialects/postgresql/base.py`, `dialects/mssql/base.py`.
- Data residency — `docs/architecture/deployment-residency.md` (metadata leaves the environment only
  as the model's input; stage 1 reads no row).
