---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP110 — An AdventureWorks data loader in the repository (C23)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C23 recorded 2026-10-22: every chain build and the demo need Microsoft's AdventureWorks CSVs in the
warehouse, and the loader was a session script (`pg_load_all.py`, 2026-10-18), not in the repo. WP96 built the schema
half (`eval.adventureworks.postgres_ddl`); this is the data half.

## 1 What the source says, read before the change

Microsoft's install script (`instawdb.sql`, read at `master` on 2026-10-31) loads 68 CSVs with `BULK INSERT`, all
`CODEPAGE = '65001'` (UTF-8) and `DATAFILETYPE = 'char'`, in two terminator pairs: 54 tables `FIELDTERMINATOR '\t'`
(49 with `ROWTERMINATOR '0x0a'`, 5 with `'\n'` — the same byte), 14 tables `'+|'` / `'&|\n'` (BusinessEntity,
BusinessEntityAddress, BusinessEntityContact, Document, EmailAddress, Illustration, JobCandidate, Password, Person,
PersonPhone, PhoneNumberType, ProductModel, ProductPhoto, Store — the ones with free text, XML or binary). Three files
inspected: `ProductReview.csv` (4 records, 34 line feeds — comments with embedded LF under a LF row terminator),
`Document.csv` (12 records, rows ending `&|\r\n`, the hierarchy root exported as a NUL byte), `CountryRegion.csv`
(plain). The local copy the chains build against (`vault`, loaded by the session script with sniffed types) holds
**759 241 rows** in 68 tables; the exact count per table is the reference for P2.

## 2 The rules

1. **The install script's options are transcribed into the extract.** `extract.py` reads each `BULK INSERT`'s
   `FIELDTERMINATOR`, `ROWTERMINATOR` (`0x0a` normalised to a line feed) and `CODEPAGE` into `bulk_insert` per table;
   `schema_extract.json` is regenerated — additive, nothing else moves (the derived cases stay byte-identical, WP30
   §3.4's guard). Transcribed, never curated: the loader reads what Microsoft wrote.
2. **Decoding and splitting follow the options, with three tolerances the files need.** UTF-8 by the codepage, a
   BOM honoured when present (UTF-8 or UTF-16). A `'&|\n'` row ends at `&|`, the line end after it (`\n` or `\r\n`)
   dropped; a `'\n'` row that has fewer fields than the table's columns continues on the next line (the ProductReview
   comments). A trailing `\r` on a record's last field is dropped. An empty field is NULL (BULK INSERT's `char` rule);
   a field that is one NUL byte is the hierarchy root `/` — `hierarchyid.ToString()`'s spelling of the value Microsoft
   exported as a NUL, and PostgreSQL `text` cannot hold a NUL.
3. **The catalogue is the DDL instrument's.** The loader creates the schemas, tables, keys and unique indexes with
   `postgres_ddl.render_ddl(..., foreign_keys=False)`, adds `load_datetime timestamp NOT NULL DEFAULT now()` and
   `record_source text NOT NULL DEFAULT 'adventureworks'` to every table, copies the CSVs (`COPY … FROM STDIN WITH
   (FORMAT csv, NULL '')`, the DDL's columns in order, lowercase and quoted as the generated projects fold them), and
   applies the 90 foreign keys last (`render_foreign_keys`) — so load order needs no topology and a violated key fails
   the load loudly. One value conversion by type: a `varbinary` `0x…` becomes PostgreSQL's `\x…`. `render_ddl()`'s
   default output stays byte-identical.
4. **Network and files.** The CSVs are fetched from the install script's repository (the same `raw.githubusercontent`
   base `extract.py` documents) into a cache directory and never re-fetched when present; `--csv-dir` points at files
   already on disk. The fetch and the connection are injected, so the module is tested without either.
5. **The command.** `python -m eval.adventureworks.load_postgres --url postgresql://… [--csv-dir DIR] [--replace]
   [--tables A,B]`: `--replace` drops the five schemas first (never the default); the run prints a row count per table
   and the total. psycopg2 (installed with SQLAlchemy's PostgreSQL extra) does the COPY.

## 3 Not this WP

Databricks as a second target (the owner's workspace is quota-bound, 9.6); the session script's sniffed types (the
instrument's transcription is the catalogue now — P3 shows the generated vault does not care); a loader for other
datasets; the demo's frozen runs.

## 4 Acceptance (keyless)

`tests/test_wp110_adventureworks_loader.py`, committed red: the options parsed from a script snippet; every table of
the checked-in extract carrying them, the fourteen `+|` tables named; BOM-aware decoding; `+|`/`&|` records with
embedded CRLF and the line end after the terminator; LF records joined to the width; the NUL root; `bytea`
conversion; the COPY statement and its CSV payload; the DDL split byte-identical with 90 foreign keys; the load
against a fake connection and fetch: schemas and audit columns before the first COPY, keys after the last, counts
returned, a cached file not fetched again.

## 5 Pre-registration

- **P1** (keyless) The extract regenerated from today's `instawdb.sql`: every one of the 68 tables gains
  `bulk_insert`, 14 with `+|`/`&|\n`, 54 with a tab and a line feed, all `65001`; no other key changes; the derived
  cases byte-identical.
- **P2** (network and the local PostgreSQL, a fresh database `aw_loader`) The loader fetches 68 files and loads 68
  tables; every table's row count equals the `vault` copy's, total **759 241**; ProductReview 4, Document 12; all 90
  foreign keys apply. A table whose values the DDL's type refuses (an XML declaration, a length, a GUID) is reported
  with the value, not worked around silently.
- **P3** (keyless build) The twenty-third chain's fifth project (WP107's) built against `aw_loader` and against
  `vault` in fresh schemas: PASS=421 both; the 40 hubs' and 50 links' row counts equal table for table.
- **P4** Suite green, ruff, bare mypy; `render_ddl()` unchanged (guard); NOTICE and the demo README name the loader.

## 6 Measured

Appended after the run.
