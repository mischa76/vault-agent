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

## 5 Measured (2026-11-14)

- **P1 ✔.** Seven guards red at the spec's commit, three green by design; after the build ten guards green — not
  the same ten: see rule 4.
- **P3 measured, and it falsified rule 4.** The five AdventureWorks schemas read from the local PostgreSQL 16 copy
  (`aw_source`, `source-schema` over `postgresql+psycopg2`): 68 tables, 601 columns — **`generated: false` on all
  601, `true` on none.** The copy was loaded without identities, as a landing zone or a replica is; its 40
  single-column integer primary keys are the original system's identities and the catalogue truthfully says this
  database does not generate them. Under rule 4 each of them would have been admissible, and `AddressTypeID`,
  which the requirements name first, *agreed* — the defect WP125 closes, through the back door.
  **Rule 4 is withdrawn**: `generated: false` is recorded and carried, and no rule reads it. A business number the
  database does not generate is keyed by a named answer with a reason (`--key`, `--key-reason`), and disclosed
  with that reason; two guards pin that instead of the withdrawn rule's three.
- **Changed while building:** an exact numeric (`decimal`, `numeric`, `number`) is technical by its type, like an
  integer — the type an Oracle or Db2 identity sits on, where the catalogue is silent. Before, such a primary key
  named first by the requirements would have been *agreed* as a column „whose type says nothing".
- **Rules 1–3 and 5 as specified.** The reader: `identity` or `autoincrement: True` → generated; `False` → not
  generated on PostgreSQL and SQL Server only; SQLite and every other dialect → unknown.
- **The rule on the real catalogue** (PostgreSQL spellings, lower-case names), with the twenty-third chain's
  candidates over all five schemas at once: 12 agreed (`Product=productnumber` among them), 1 natural primary key,
  **6 contested** — the same six tables as on the datasets (WP125 §5).
- **P2 ✔.** Suite with no key reachable 1774 passed / 5 skipped, ruff, bare mypy; no baseline moved.
- **Not measured:** a source with identities read through the reader (SQL Server, or a PostgreSQL with serial
  columns) — the `true` path is covered by the guards on the dialects' reflected shapes only; Oracle and Db2.
