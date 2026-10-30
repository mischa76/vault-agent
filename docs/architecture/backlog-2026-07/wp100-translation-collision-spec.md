---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP100 — Two translations in one stage whose natural keys share a name are projected apart (C33)

Status: **Approved and in progress** (2026-10-30, the owner's go on C33 first — the one of the three build findings
that produces wrong data) · Owner: Mischa Eismann · Author: Claude. Found by the C1 experiment's keyless PostgreSQL
build of arm T's fifth project (`docs/log.md`, 2026-10-30, „The audit the plan put first").

## 1 What is wrong, in one paragraph

A link staged through two or more surrogate→natural-key translations (WP36) projects each hub's natural key under
the hub's canonical key column. When two of those hubs are keyed alike — `hub_department` on `Department.Name`,
`hub_shift` on `Shift.Name`; every AdventureWorks reference table has a `Name`, and the drafted requirements keyed
fourteen hubs on it — the translation view reads `select t.*, r1.NAME as NAME, r2.NAME as NAME`, its `schema.yml`
declares the `not_null` test twice on one column, and dbt refuses to parse the project. Had it parsed, PostgreSQL
would have refused the view too; had the view been accepted, the stage would have hashed `SHIFT_HK` and
`DEPARTMENT_HK` from one column, and the link's own hash key over `NAME, NAME` — **wrong data**, the class WP24 named
the only one that matters. Five of arm T's 42 translation views collide, all on `NAME`
(`EmployeeDepartmentHistory` through `Department` and `Shift`, twice; `SalesOrderHeader` through five tables;
`CountryRegionCurrency`; `ProductModelProductDescriptionCulture`). WP89 solved the same collision between a
translated key and the *relation's own* homonym (`<KEY>_VIA_<THROUGH>`); between two translations nothing did.

## 2 The rules

1. **Pushed apart at the moment the participation is staged.** Within one stage, translated participations are
   visited in the link's participation order. A translation whose projected column — the hub's canonical key
   column, or the role column for a role-qualified participation (WP41) — normalises equal to a column an earlier
   translation of the same stage already projects is projected as `<KEY>_VIA_<THROUGH>` (`NAME_VIA_SHIFT`), the
   same form WP89 uses. The first keeps the plain name: a single translation stays byte-identical to today.
2. **Everything taken over it follows by construction.** The hub's foreign hash key (`SHIFT_HK`), the link's hash
   key list, the null group (WP83/WP93) and the `not_null` test name the pushed-apart column, because the column is
   renamed *before* any of them is recorded — not replaced afterwards, where the second `NAME` could not be told
   from the first. A composite key (WP93) is checked column by column.
3. **Both sites.** The link's own stage and a link satellite's dedicated stage (WP40, `source_table` on a link
   satellite) apply the rule; a hub satellite's stage carries one translation and has nothing to collide with.
4. **WP89 runs after and sees the result.** When the relation also carries the homonym (`EmployeeDepartmentHistory`
   with its own `Name` beside two translated `Name`s), WP89 pushes the first apart from the relation
   (`NAME_VIA_DEPARTMENT`) and leaves the already-renamed second alone (`NAME_VIA_SHIFT`).
5. **The view is never rendered with a duplicate projection.** `render_translation_model` asserts the projected
   aliases are distinct — reaching that assertion is a generator defect, and the run stops there instead of
   handing a warehouse a view it will refuse (or, worse, accept).
6. **Visible, not flagged.** As for WP89: the rename is in the SQL, the stage's `hashed_columns` and the stage
   entry's `key_translation.joins[].projects` in `metadata/automatedv.yml`; no new flag, no new gate — nothing
   about the model is wrong, only the generator's naming was.
7. **Not in this WP:** a third unqualified translation through the *same* table projecting the same name (two
   would be `NAME` and `NAME_VIA_X`; a third would collide with the second — rule 5 stops it; the shape needs
   roles, WP41). `dbt parse` as an eval gate (C34's second half).

## 3 Acceptance (keyless)

`tests/test_wp100_translation_collision.py`, committed red before the change: the view projects
`r1.NAME as NAME, r2.NAME as NAME_VIA_SHIFT`; the stage hashes `SHIFT_HK` over `NAME_VIA_SHIFT`, `DEPARTMENT_HK` over
`NAME`, the link key over both; the `schema.yml` declares each projected column once; the link satellite's stage
follows; the metadata records both projections; no rendered translation view projects one alias twice; with the
relation carrying its own `Name`, WP89 and this rule together yield `NAME_VIA_DEPARTMENT` and `NAME_VIA_SHIFT`. The
rest of the suite unchanged — every byte-identity fixture carries at most one translation per projected name.

## 4 Pre-registration (keyless, PostgreSQL 16, the local data copy)

Arm T's fifth project (`20261030T184653223619Z`, step 5) regenerated from its kept artefacts — the step's model, the
sales increment's declared schema, the fourth step's model and catalogue as `--existing` would read them, the
step's mapping proposals — through the mapper's re-bind (`rebind_staging`), built into a fresh schema `c1_t_wp100`:

- **P1** the regenerated staging differs from the kept staging in exactly the five colliding views, their five
  `schema.yml` files and the stages that read them (hash columns renamed) — nothing else. (The contracts are not
  reconstructed; they pin seed types, not staging SQL. A difference beyond the five is listed, not explained away.)
- **P2** each of the five views projects distinct aliases; `dbt parse` succeeds.
- **P3** `dbt build`: no error names a translation view or a stage reading one. Not predicted: the other errors —
  arm T disclosed one inferred stage (C18's class), and the C34/C35 classes arm A showed may be in arm T too; each
  is listed in the log.
- **P4** for each of the five links: every `<HUB>_HK` of a pushed-apart participation joins its hub (0 orphans
  where the surrogate is not NULL), the link's row count equals the relation's distinct key rows — the data the
  collision would have made wrong, shown right.
- **P5** `uv run pytest` green with no fixture updated.

Not predicted: wall time; the total PASS count.
