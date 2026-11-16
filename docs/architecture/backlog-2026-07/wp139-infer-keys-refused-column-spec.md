---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP139 — `infer-keys` leaves out the column the database refuses to count, not its table (C76)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C76) · Owner: Mischa
Eismann · Author: Claude. Candidate C76. Of the candidate's two options the second is taken — the table is
read again without what was refused — in the form the profiler has had since WP98 (§2).

## 1 What is wrong — measured

`key_inference._reflect` counts `count(*)`, and `count(c)` and `count(distinct c)` for every column, in one
statement per table. PostgreSQL has no equality operator for `xml` and refuses the statement
(`UndefinedFunction`); the function then names the table on stderr and returns nothing for it. On the data
copy that is five of 68 tables — `Person.Person`, `Sales.Store`, `Production.ProductModel`,
`Production.Illustration`, `HumanResources.JobCandidate`, seven `xml` columns between them
(`information_schema.columns`, read 2026-11-16). Two consequences:

1. The five tables get no inferred unique key and no inferred foreign key for any of their columns.
2. Their columns are no key columns: nothing can be inferred as a reference into `Person`, the table most
   referenced in the catalogue, nor recorded as tied with or wider than it. A declared primary key does not
   help — the key list is built from the tables that were read.

WP99 read all 68 tables on 2026-10-30 (139 inferred unique keys, 95 inferred foreign keys); the numbers of
WP136 to WP138 are of 63. What changed in the copy between is not looked into here. The profiler meets the
same refusal and has always answered it per column: the profile omits the `xml` columns and keeps the rest
(`profiler._profile_table`, WP98; seen in `docs/log.md`, 2026-11-07).

## 2 The rule

**A refused table is counted again column by column; a column still refused is named on stderr and left
out.** As in the profiler: after the refusal, `count(*)` alone, then one statement per column. A column
without counts is no inferred unique key, gets no inferred foreign key and is no key column; every other
column of the table is read as if the refusal had not happened. A table whose `count(*)` is refused stays as
it is — named, left without inferences.

Chosen over the candidate's first option (count only the type families the inference reads): a `uuid` or a
boolean column is of the family `other` and can be an inferred unique key today (`rowguid`); not counting it
would change what the command writes for every table, to repair five.

**Unchanged.** Every table the database does not refuse: one statement, the same counts, the same file. The
candidate tiers, the inclusion check, WP137's and WP138's rules.

## 3 Not built

- **No list of types without equality.** Which types a database cannot compare is the database's to say
  (WP121 found nine on PostgreSQL); the refusal is the test.
- **No inference on a refused column by another route** (casting `xml` to text): what is equal in such a
  column is not this command's to define.
- **The proposer and the pipeline** are untouched; a file written before this change lacks the five tables'
  inferences until the command runs again.

## 4 Pre-registration

- **P1** (keyless, SQLite through the real inference; the refusal injected at the cursor, since SQLite
  refuses nothing): `Doc(DocID, Title, Body)` with `count(DISTINCT Body)` refused, `Page(PageID, DocID)`.
  Today `Doc` is left without inferences and `Page.DocID → Doc.DocID` is not inferred. After: `Doc` carries
  its unique keys `DocID` and `Title`, `Page.DocID → Doc.DocID` is inferred (3 rows, 2 distinct, 3
  referenced), stderr names `main.Doc.Body` once and no table. **Red before the change.** A table whose
  every statement is refused is still named and left without inferences — green before and after.
- **P2** (keyless): the guards of WP99, WP137 and WP138 unchanged and green.
- **P3** (local PostgreSQL, by hand, read-only): `infer-keys` over the full catalogue against the data copy
  reads **68 of 68 tables** and names exactly the seven `xml` columns. The 64 inferred unique keys of before
  are all there, with those of the five tables added. Inferred foreign keys: the same **4**, each equal to
  its earlier entry — every column of the catalogue that points at one of the five tables by name has a
  declared key (WP137 infers nothing there); a fifth would be a key the catalogue lacks and is not expected.
  Two runs byte-identical.
- **P4** (the same, the catalogue with every declared key removed — WP99's case): WP99 recorded 139 inferred
  unique keys and 95 inferred foreign keys on 68 tables, three of the 95 false (WP138). Predicted, if the
  copy's rows are those of 2026-10-30: **139 and 92** (127 and 83 on 63 tables); nothing inferred on 63
  tables is lost, though a reference may now name a tighter target among the five.
- **P5** (zero cost, the stored chain): with the new file the proposer offers the same 2 inferred licences
  and 60 and 30 declared; WP136's replay writes the fifth project byte-identical to the built one.

No paid run: nothing here touches a model call.

## 5 Measured (2026-11-16)

All keyless, no model call. Evidence: `eval/results/kept-outputs/wp139-20261116/`.

- **P1 held.** Three of the four guards red at `17b8fd9`, four green with the change; the pin green on both.
- **P2 held.** The guards of WP99, WP137 and WP138 unchanged and green. Suite 1859 passed, 3 skipped with no
  key reachable; `ruff check --no-cache` and a bare `mypy` clean; no byte-identity fixture changed.
- **P3 held.** `infer-keys` over the full catalogue against the data copy: **68 of 68 tables read**, exactly
  the seven `xml` columns named, each with `UndefinedFunction`. 68 inferred unique keys — the 64 of before and
  four of the five tables (`rowguid` of `Person`, `Store`, `ProductModel`; `Illustration.modifieddate`). The
  same 4 inferred foreign keys, each equal to its earlier entry; no fifth. Two runs byte-identical.
- **P4 missed.** Predicted 139 inferred unique keys and 92 inferred foreign keys on the catalogue without
  declarations; measured **137 and 94** (127 and 83 with the table-level refusal patched back in). The
  prediction was conditional on the copy's rows being those of 2026-10-30, and they are not:
  `Person.Person` has 19 972 rows where WP99 recorded 19 973, and `ProductReview.productid` is `integer`
  where WP99 recorded `text`. WP99's file was not kept, so the difference of two on each side cannot be
  reconciled pair by pair. What the comparison on today's copy does show: nothing inferred on 63 tables is
  lost; **eleven inferred foreign keys are gained**, seven of them references into `Person`, `Store`,
  `ProductModel` and `Illustration` from other tables and four on columns of the five tables; ten of the
  eleven name exactly the target AdventureWorks declares for the column, the eleventh
  (`Person.businessentityid`) names a table of equal domain and carries the declared one as wider. Ten
  earlier inferences gain `Person.businessentityid` in their tied or wider list; ten unique keys are
  gained; no pair within one table.
- **P5 held.** The proposer over the stored chain with the new file: the same 2 inferred licences, 60 and 30
  declared. WP136's replay writes the fifth project byte-identical to the built one.
- **Not measured.** A database other than PostgreSQL refusing a count (the guard injects the refusal on
  SQLite); the type tier against the data copy; why the copy differs from the one of 2026-10-30.

### Corrected (2026-11-16, found during WP140): P4 holds — it was measured on the wrong copy

There are two local copies. WP99 measured on the database `vault` (key-less, `Person.Person` 19 973 rows,
`ProductReview.productid` `text`, no `xml` column); the measurement above was taken on `aw_source` (90
declared foreign keys, 19 972 rows, `integer`, seven `xml` columns). Nothing changed between 2026-10-30 and
today. Today's code over the catalogue without declarations against `vault`: 68 of 68 tables read, **139
inferred unique keys and 92 inferred foreign keys**, none within one table — the prediction, exactly. „P4
missed" and „why the copy differs from the one of 2026-10-30" above are wrong in that sense; the numbers for
`aw_source` (137 and 94, eleven gained over the table-level refusal) stand as measurements of that copy.
`docs/log.md`, 2026-11-16, „Correction to WP139".
