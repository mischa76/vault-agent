---
type: spec
status: not-measured
updated: 2026-11-15
---

# WP130 — A sign-off binding is checked against the columns a stage reads, not against expression text (C66)

Status: **Approved and in progress** (2026-11-15, within the owner's instruction to regenerate the shipped demo —
the chain is paused at the sign-off this blocks) · Owner: Mischa Eismann · Author: Claude. Candidate C66.

## 1 What is wrong

WP82 lets a human bind a stage no rule could bind (`resume --bind`, the workbench's sign-off). The check
(`bindings.check_stage_bindings`) asks `stage_key_needs` which columns the relation must carry; that function reads
every derived column's source from the stage's stored metadata. Since WP123 (hashdiffs keep the letter case) every
column a hashdiff reads is a derived column whose value is an expression —
`ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALCOST AS text)), ''), 'UTF8'), 'hex')` — and the function took that text
for a column name. Every binding of a stage that carries a hashdiff is refused („declares none of ENCODE(…)"), and
the checkpoint shows the human the expressions as „expected columns". WP123 gave the validator's gate
(`E_STAGE_COLUMN_NOT_IN_SOURCE`) the metadata's typed `expression_reads` for exactly this; `stage_key_needs` is a
second derivation of the same reading and was not touched. Found on 2026-11-15 at the third step's sign-off of the
demo's chain: `stg_work_order_operation` could not be bound to `WorkOrderRouting`, which carries every column it
reads.

## 2 The rules

1. `stage_key_needs` returns relation columns only: a derived column with an entry in `expression_reads` contributes
   the columns that entry names; any other derived column its source, as before; a hash key's columns as before.
2. The validator's gate reads the same helper — one derivation, not two.
3. Unchanged: which bindings are refused for a column the relation really lacks; the message names the column.

## 3 Pre-registration (keyless)

- **P1** guards (`tests/test_wp130_binding_reads_columns.py`) red first — the alias case green by design — then green.
- **P2** suite, ruff, bare mypy green with no key reachable; WP73's, WP82's and WP123's guards unchanged.
- **P3** live: the paused run of the demo's chain accepts the binding `stg_work_order_operation` →
  `WorkOrderRouting` and finishes green.

## 4 Measured (2026-11-15)

- **P1 ✔.** Four of five guards red at `dcd5ae3`, five green after.
- **P2 ✔.** Suite with no key reachable, ruff, bare mypy (numbers in `docs/log.md`); WP73's, WP82's and WP123's
  guards unchanged and green.
- **P3 ✔ live.** The workbench was restarted on the fixed code while the run stayed paused; its checkpoint then
  named ten columns for `stg_work_order_operation` instead of expressions, the binding to `WorkOrderRouting` was
  accepted, the run finished green and the stage's metadata says `source_binding: declared`. The stage built on
  PostgreSQL with the fifth project.
- **Built as specified:** `bindings.stage_key_needs` is the one reading; the validator's gate calls it.
