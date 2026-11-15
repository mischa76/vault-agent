---
type: spec
status: not-measured
updated: 2026-11-15
---

# WP133 — The satellite grain gate judges a stage that reads through a translation view (C69)

Status: **Approved and in progress** (2026-11-15; not named in the owner's go of that day — C67 and C68 — but the
same defect class as C68, found while verifying them, and the demo's chain cannot build cleanly without it; the
owner is told with the result) · Owner: Mischa Eismann · Author: Claude. Candidate C69.

## 1 What is wrong

WP85's gate (`E_SAT_GRAIN_NOT_UNIQUE`) refuses a satellite whose key does not cover a unique key of the relation
it reads: such a satellite holds several rows per key and load date and re-inserts on every load. Its case was the
owner's bill of materials (C13): a link on (assembly, component, unit) over a table unique on (assembly,
component, StartDate), +195 rows per build. Like WP73's gate it skipped every stage that reads through a
translation view — the stage's key columns are then the view's projected natural keys, which the relation does not
carry, and the gate had no way back to the relation's columns.

Since WP125 `hub_product` is keyed on the product number, so the bill of materials reads through a translation:
the very case the gate was built for is no longer judged. The demo of 2026-11-15 did not show it — C67 failed the
stage, so the satellite was skipped. With C67 repaired (WP131) the replayed project builds, and its second build
inserts 343 rows into `sat_product_assembly_component_details` (the first, 195 more than once per key).

## 2 The rules

1. The stage's metadata says, typed, which column of its own relation each translated key stands for: every join
   of `key_translation` gets `reads` — the referencing column (`PRODUCTASSEMBLYID` for the projected
   `PRODUCTNUMBER`). The join's `on` stays what it is, a text for the reader; nothing parses it.
2. The grain gate maps a satellite's key columns back to the relation as before (through derived columns) and
   then through `reads` (`bindings.translation_reads`): a translated key counts as its referencing column. A
   composite key's projected columns all stand for the one referencing column.
3. A stage whose metadata carries a translation without `reads` — stored before this WP — is not judged, as
   before; never guessed.
4. Unchanged: the gate's severity, message form and remedy (multi-active with the missing unique-key columns as
   child-dependent key); stages without a translation; existing constructs and effectivity satellites.

**Output-changing in the metadata only:** `metadata/automatedv.yml` gains one key per translation join. No model,
no SQL, no hash changes.

## 3 Why a translated key may stand for its referencing column

The translation joins the referenced relation on its surrogate and projects the hub's natural key, which is a
declared unique key of that relation (ADR-0021 — it is why the hub is keyed on it). Surrogate and natural key
identify the same row, so a set of rows is unique on the one exactly when it is unique on the other. A NULL
surrogate is a zero-key participant on both readings.

## 4 Pre-registration

- **P1** guards (`tests/test_wp133_translated_satellite_grain.py`) red first — two of five; the three that pin
  what stays (the remedy followed, a covering key, metadata without `reads`) green by design — then green.
- **P2** suite with no key reachable, ruff, bare mypy; WP85's guards unchanged.
- **P3** zero-cost replay of the demo's five stored runs: the gate fires on `sat_product_assembly_component_details`
  in step 3 and on no other satellite of a translated stage in any step.
- **P4** live: in the demo's next chain the modeler is refused that satellite (or builds it multi-active at once),
  follows the remedy, and the project's second build inserts nothing (recorded in `docs/log.md`).

## 5 Measured (2026-11-15)

- **P1 ✔ with a deviation.** Three of five red at `0ee6123`, not the two announced: the guard for metadata
  without `reads` deletes the field and so failed on its absence. Five green after.
- **P2 ✔.** Numbers in `docs/log.md`.
- **P3 ✔.** One fire on a translated stage over five steps: `sat_product_assembly_component_details` in step 3
  („unique on ProductAssemblyID + ComponentID + StartDate, but its key covers only COMPONENTID, PRODUCTASSEMBLYID,
  UNITMEASURECODE"). Steps 1, 2, 4, 5: none. (Step 3's second fire, on `sat_work_order_operation_details`, is
  the replay knowing the sign-off binding — WP132 §5, C70 — and not a translated stage.)
- **P4** in `docs/log.md` with the chain.
- **P4 ✔ live** (2026-11-15, the demo's second chain; `docs/log.md`). Read from the traces: in step 3 the
  modeler's first draft was refused `sat_product_assembly_component_details` (`E_SAT_GRAIN_NOT_UNIQUE`), the second
  call made it multi-active with `StartDate` as child-dependent key; in step 2 the same on
  `sat_business_entity_department_shift_details` (a stage translating `DepartmentID` and `ShiftID`). Two fires on
  translated stages, both followed in the next attempt; two more in step 3 on stages without a translation (WP85's
  ordinary case). The fifth project's second build inserts nothing (186 of 186 incremental models `INSERT 0 0`);
  the bill of materials' satellite holds 2 679 rows, the table's.
