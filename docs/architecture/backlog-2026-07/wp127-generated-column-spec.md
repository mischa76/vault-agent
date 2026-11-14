---
type: spec
status: not-measured
updated: 2026-11-14
---

# WP127 — The catalogue says whether a column is generated; the key rule reads it before the type (C63, ADR-0021)

Status: **Approved and in progress** (2026-11-14, on the owner's go on the proposal as presented) · Owner: Mischa
Eismann · Author: Claude. Candidate C63; ADR-0021's consequence „until the reader delivers it the rule reads the
type".

## 1 What is wrong

WP125 decides whether a key is technical by its type: an integer or a GUID is taken as the source system's own, a
character column as a code. Two cases go wrong. A generated key of another type — an identity on a `numeric`, the
ordinary shape on Oracle and Db2 — is evidence for nothing, so its table is never contested. And an integer key the
business assigns — a customer number the database does not generate — is taken as technical: where the requirements
name it, the rule does not agree, and the hub is disclosed as sitting on a technical key it does not sit on.

## 2 The rules

1. **`SourceColumn.generated`**: `true` when the database generates the value, `false` when the catalogue says it
   does not, absent when it cannot say. Carried by the house file (`generated:` on a column, omitted when unknown)
   and by the travelling catalogue; a file without it loads and renders as before.
2. **The reader** (`InspectorReader.columns`) reads SQLAlchemy's reflection, verified against the installed 2.1.6:
   a column with an `identity` entry or `autoincrement: True` is generated
   (`engine/interfaces.py`, `ReflectedColumn`). `autoincrement: False` means *not generated* only on a dialect
   whose reflection derives the flag from the catalogue — PostgreSQL (`dialects/postgresql/base.py`: a `nextval`
   default on an integer, or an identity) and SQL Server (`dialects/mssql/base.py`: `is_identity`). SQLite's
   reflection sets it to `False` for every column (`dialects/sqlite/base.py`), so there and on any other dialect a
   `False` is recorded as unknown. A value a trigger or the application generates is not in the catalogue; it reads
   as not generated, which is why rule 4 needs the requirements as well.
3. **A generated column is technical**, whatever its type.
4. **An integer primary key the catalogue says is not generated, and that is no reference to another table's
   technical key, is admissible**: where the requirements' first choice names it, the key is *agreed* — a business
   number — and the hub is not disclosed as technical. Where they do not, it stays what the type says: with a
   declared natural key beside it the case is contested, as in WP125.
5. Without the property nothing changes: every decision of WP125 on a catalogue that does not carry it is the same.

## 3 Not done

No reader for a catalogue that is not a SQLAlchemy reflection. No reading of triggers or sequences without a
default. The AdventureWorks datasets are derived from an extract that does not carry the identity property and are
left as they are; the chain's decisions do not depend on it (every key WP125 contests there is an integer identity).

## 4 Pre-registration

- **P1** guards (`tests/test_wp127_generated_column.py`) red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable; no baseline moves — in particular the catalogue files
  written by `source-schema` from SQLite (it cannot say) and every dataset's decisions under WP125.
- **P3** on the local PostgreSQL copy of AdventureWorks, if reachable: the catalogue read by `source-schema` marks
  the identity and serial columns generated and the rest of the integer columns not generated; recorded with the
  counts, or as not measured with the reason.
