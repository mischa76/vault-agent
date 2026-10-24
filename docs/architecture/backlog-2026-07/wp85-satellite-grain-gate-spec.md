---
type: spec
status: not-measured
updated: 2026-10-22
---

# WP85 — A satellite whose key does not cover a unique key of its relation is refused (`E_SAT_GRAIN_NOT_UNIQUE`, C13)

Status: **Approved and in progress** (2026-10-22, the owner's word: what matters is that the software now works correctly; comparability with earlier tests matters only in that the software no longer repeats its predecessors' errors) · Owner: Mischa Eismann · Author: Claude. Backlog C13.

## 1 What is wrong

`sat_product_assembly_component_details` hangs off the (assembly, component, unit) link while
`BillOfMaterials` is unique only on (assembly, component, `StartDate`): 195 keys recur, the standard satellite
holds several rows per key and load date and re-inserts on every run (+195, +339 in the owner's build; +195 again
after WP83/WP84). Nothing refuses it: no gate compares a satellite's key with its relation's unique keys, and the
catalogue does not carry them. A correction found on the way: the AdventureWorks extract has **no primary key for
any table** and misses the composite alternate key — `_PK_RE` expects `] ADD CONSTRAINT [PK_…]` while the install
script writes `] WITH CHECK ADD` (71 statements), and `_AK_RE` matches `CREATE UNIQUE INDEX` but not
`CREATE UNIQUE CLUSTERED INDEX` (`AK_BillOfMaterials_ProductAssemblyID_ComponentID_StartDate`, two `IX_`).
The same class as the 2026-09-12 foreign-key fix. Prompts are not affected: the schema section renders table and
column names only (`grounding.render_schema_prompt_section`), the mapper types and comments.

## 2 The rules

1. **The catalogue carries keys.** `SourceTable.primary_key: list[str]` and `unique_keys: list[list[str]]`,
   empty by default (every earlier input byte-identical). The extract reads every primary key and every unique
   index (`CREATE UNIQUE [CLUSTERED|NONCLUSTERED] INDEX`); `derive.py` writes `primary_key` and the
   non-technical unique keys (row GUIDs excluded, as for natural keys) into each case's `source_schema.yml`.
2. **`E_SAT_GRAIN_NOT_UNIQUE`** — for a satellite of this increment (not pre-existing, not effectivity) whose
   stage is declared-bound to a relation of this increment that declares at least one unique key (primary or
   unique): the relation columns its key is taken over — the stage's parent-hash columns mapped back through
   derived columns, plus its child-dependent key — must include every column of at least one unique key. Else
   an error naming the uncovered key and a remedy: make it multi-active with the missing columns as its
   child-dependent key, or hang it on a parent whose key covers the relation's grain. Translated stages and
   relations without declared keys: no check.
3. A gate, not a backstop: the data would be wrong (duplicates per key and load date, non-idempotent), and the
   modeler can answer it in the bounded re-model loop.

## 3 Acceptance (keyless)

`tests/test_wp85_satellite_grain.py`: the bill-of-materials shape is refused, its multi-active form with
`StartDate` passes; a hub satellite on the primary key passes; a relation without keys passes; a pre-existing
satellite is not judged; the extract finds the primary key and the composite unique index in Microsoft's SQL
text; derive writes them.

## 4 Pre-registration

- **P1** the re-run extract: every one of the 68 business tables has a primary key; `BillOfMaterials` has the
  unique key (ProductAssemblyID, ComponentID, StartDate).
- **P2** the gate on the owner's five steps, each run's model and increment from `demo/workbench-adventureworks/`
  with the re-derived keys and the generator of today: it fires on exactly these satellites —
  `sat_business_entity_department_shift_audit` (HR; `EmployeeDepartmentHistory` is unique on
  BusinessEntityID, StartDate, DepartmentID, ShiftID), `sat_product_assembly_component_details` (Production),
  `sat_business_entity_sales_territory_assignment_details` and `sat_shopping_cart_product_details` (Sales) —
  and on nothing in Person and Purchasing.
- **P3** the bill-of-materials satellite rewritten as the remedy says (multi-active, child-dependent key
  `StartDate`), the Sales project regenerated and built twice into a fresh schema: the satellite `INSERT 0 0` on
  the second build — 180 of 180 incremental models idempotent.
