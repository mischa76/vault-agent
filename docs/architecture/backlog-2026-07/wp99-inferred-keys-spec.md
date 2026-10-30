---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP99 — Keys inferred from data: unique columns and inclusion dependencies, their own class, proposed and never accepted by default (C27 stage 3)

Status: **Approved and in progress** (2026-10-30, the owner's go: „weiter mit C27 stage 3") · Owner: Mischa Eismann ·
Author: Claude. Backlog C27 stage 3; ADR-0018 (proposed, built on its recommendation — Option B). Builds on the
proposer (WP34–WP40, WP46), the profiler (WP98), the catalogue command (WP96) and the checkpoint's decision applier.

## 1 What is wrong, in one paragraph

The proposer reads declared foreign keys and nothing else, so a source without declarations — the house's own
AdventureWorks data copy has 68 tables and 0 keys — gets no link proposals, no licences, and link stages that bind
by nothing (C18's `none`). The data says what the catalogue does not: a column that is unique and non-null over all
rows, and a column whose every value occurs in such a key column. Reading that is an inference, and the product has
no class for an inference about keys — only declarations and WP34's rejected name-only tier.

## 2 The rules

1. **The class.** `InferredUniqueKey(columns, rows)`; `InferredForeignKey` — a `ForeignKeyRef` plus `rows` (the
   non-null referencing rows, every one found in the referenced column), `distinct` (distinct referencing values),
   `referenced_distinct`, `candidate` (`name` or `type`) and `wider` (`Table.column` of every other unique column
   that also contains every value; the inference is the tightest); `InferredKeys(unique, foreign)`;
   `SourceTable.inferred_keys: InferredKeys | None`, absent by default, accepted by the loader under
   `inferred_keys:`, rendered by the house renderer after the declared keys. `LinkProposal.provenance` and
   `KeyLicense.provenance`: `declared` (the default, every existing shape byte-identical) or `inferred`.
2. **The command.** `vault-agent infer-keys --source-schema FILE --out FILE [--url] [--candidates name|type]`:
   reads the declared schema file, reflects every table it names from the database, infers, and writes the file
   back in the house rendering with the inferences attached and a provenance header naming both reads. The URL as
   for `profile`; no URL exits 2, a table the database lacks is named on stderr and left without inferences, a
   missing driver or a refused connection exits 1.
3. **Unique keys.** Over a table with more than one row, a column whose `count(distinct c) = count(c) = count(*)`
   is an inferred unique key, unless it is already the declared primary key or a declared single-column unique
   key. Composite unique keys are not inferred.
4. **Foreign keys.** For a referencing column R.c and a key column T.k — T.k declared (single-column primary or
   unique key) or inferred unique, (T, k) ≠ (R, c), the same type family by SQLAlchemy's reflected class (number,
   temporal, text) — the pair is checked when it is a *candidate*: tier `name` when `compact(c) == compact(k)`,
   or `compact(c)` ends with `compact(k)` and is longer, or `compact(c) == compact(T) + "ID"`; tier `type` when
   the families match at all (`compact` keeps letters and digits, uppercased). The anti-join
   `count(*) FROM R WHERE R.c IS NOT NULL AND NOT EXISTS (SELECT 1 FROM T WHERE T.k = R.c)` must be 0 with at
   least one non-null row. Of the holding candidates for one R.c, the one with the smallest `referenced_distinct`
   is the inference (ties: all of them); the others are its `wider`. A pair the table already declares as a
   foreign key is never inferred. Deterministic: tables by (schema, name), columns in ordinal order, candidates
   by (schema, table, column).
5. **The proposer.** After the declared keys of a table, its inferred foreign keys run the same per-key path
   (`_propose_for_key`) with `provenance="inferred"`; the first evidence line states the numbers and that no
   declaration exists. A pair that duplicates a declared key is skipped silently (the declaration already
   proposed it). Relationship-table proposals (WP37) read declarations only. Greenfield: inferred licences, same
   provenance.
6. **Never binding on its own.** In `apply_link_decision`, `accept` ratifies pending proposals and licences whose
   provenance is `declared` and sets the inferred ones to `overridden`; an explicit `links[key]` decides either
   way. The interactive prompt defaults to *no* for an inferred proposal and prints the provenance; the
   workbench's pending list carries the provenance. The eval's unattended resume therefore builds nothing from an
   inference; `link_proposals` metrics gain `by_provenance`.
7. **Inert where unread.** `render_schema_prompt_section`, `dump_source_catalogue` and `build_staging` are
   byte-identical with and without inferred keys (the WP34 pins, extended). `E_SAT_GRAIN_NOT_UNIQUE` reads declared
   keys only (ADR-0018 §3).

## 3 Not this WP

Composite inferences. Ranking beyond „the tightest wins". The satellite-grain gate or the binder's offer tier
reading inferred unique keys (each an inference acting alone; its own WP). C1. A source-driven mode. SAP.
`candidates=type` measured live (keyless only; the manual says it is complete and noisy).

## 4 Pre-registration

- **P1** (keyless, SQLite, the inference): a six-table miniature — `BusinessEntity(1–6)`, `Person(1–5, Name with
  a duplicate)`, `Employee(1–3)`, `SalesPerson(1–2)`, `Customer(CustomerID 1–3, PersonID ∈ {2, 3, NULL})` with a
  **declared** key `PersonID → Person.BusinessEntityID`, `SalesOrderHeader(SalesOrderID 1–4, SalesPersonID ∈ {1, 2,
  NULL}, CustomerID ∈ {1, 99}, Status ∈ {1, 2})`. Tier `name` infers exactly: `Employee.BusinessEntityID →
  Person.BusinessEntityID` (rows 3, distinct 3, referenced 5, wider `BusinessEntity.BusinessEntityID`);
  `SalesPerson.BusinessEntityID → Employee.BusinessEntityID` (wider Person, BusinessEntity);
  `Person.BusinessEntityID → BusinessEntity.BusinessEntityID`; `SalesOrderHeader.SalesPersonID →
  SalesPerson.BusinessEntityID` (the table-name rule, rows 2); **not** `SalesOrderHeader.CustomerID` (99 is absent:
  no inference without full inclusion); **not** `Customer.PersonID` (declared). Unique: every `BusinessEntityID`,
  `CustomerID`, `SalesOrderID`; not `Person.Name`, not `Status`. Tier `type` additionally infers
  `SalesOrderHeader.Status → SalesPerson.BusinessEntityID` with `candidate: type` and a wider list — the noise,
  labelled. Red before the change (no module).
- **P2** (keyless, the proposer and the applier): an inferred key to an existing hub yields a proposal with
  `provenance == "inferred"` and the numbers in its first evidence line; greenfield yields an inferred licence; an
  inferred pair duplicating a declared one yields the declared proposal only; `apply_link_decision({"accept":
  True})` accepts the declared and overrides the inferred; `{"links": {key: True}}` accepts the inferred; the
  prompt defaults to *no* for an inferred proposal and to *yes* for a declared one. Red before.
- **P3** (keyless, the file and the inert surfaces): the rendered file loads back with the inferences equal; the
  modeler's schema section, the carried catalogue and the staging are byte-identical with and without inferred
  keys; the command through Typer's runner — no URL exits 2, the file written from the environment URL on the
  SQLite fixture and loaded back with its inferences. Red before.
- **P4** (local PostgreSQL 16, by hand — the ground truth): the data copy's own declared schema file (68 tables, 0
  keys, from `source-schema`) through `infer-keys --candidates name`; twice, byte-identical; the inferred foreign
  keys compared, normalised, with the extract's 89 single-column declared keys: **recall and precision reported as
  counts**, every false positive and every miss named. The expectation, counted from the extract before the run:
  the name rules reach at most 86 of the 89 (`Document.Owner`, `BillOfMaterials.ProductAssemblyID` and
  `BillOfMaterials.ComponentID` have no name path to their keys), so recall ≤ 86; the inferred unique keys
  compared with the extract's 45 single-column primary keys. Wall-clock recorded. Tier `type` not run.

## 5 Guards

`tests/test_wp99_inferred_keys.py` (P1–P3), committed red before the change; the WP34 inertness pin extended to
inferred keys with the change (deliberate update of an existing guard, said in the message). P4 by hand, in
`docs/log.md` with the lists.
