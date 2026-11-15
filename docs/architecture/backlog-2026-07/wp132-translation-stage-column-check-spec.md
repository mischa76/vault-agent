---
type: spec
status: not-measured
updated: 2026-11-15
---

# WP132 — A stage that reads through a translation view is column-checked like any other (C68)

Status: **Approved and in progress** (2026-11-15, on the owner's go of that day: fix C67 and C68, then run the
demo's chain again) · Owner: Mischa Eismann · Author: Claude. Candidate C68.

## 1 What is wrong

WP73 holds a stage to its relation: every column it hashes or derives must be declared there. It does so in two
places — where a binding is made (`staging_generator.bind_sources`, which refuses the binding, leaves the stage on
`raw_<base>` and flags `BINDING_REJECTED`), and in the validator (`E_STAGE_COLUMN_NOT_IN_SOURCE`, for a stage that
is bound when the validator runs). Both skipped a stage that reads through a translation view, because the view
adds columns the relation does not have — and nothing else judged it („judged by its own gates": there were none).

Since WP125 hubs sit on natural keys and a translation is the ordinary case: 45 of the 177 stages of the demo's
last project (2026-11-15). Its bill-of-materials stage hashed a `PRODUCTNUMBER` that neither `BillOfMaterials` nor
its view carried (C67). The stage was unbound when the validator ran, was bound to `BillOfMaterials` by the
mapper's re-bind afterwards, carried that binding into the next two steps — and PostgreSQL was the first to refuse
it.

## 2 The rules

1. What a translated stage may read is its relation's columns **plus what its view projects** — each translated
   key under its projected name (one column, or a composite key's list). Nothing else.
2. **Where a binding is made** the check runs for a translated stage too (`missing_stage_columns` counts the
   projected columns as available). A binding that fails it is refused exactly as WP73 refuses one: the stage stays
   on `raw_<base>`, `BINDING_REJECTED` names the missing column, the sign-off shows it. This is what covers the
   mapper's re-bind, which runs after the validator.
3. **The validator's gate** judges a declared-bound translated stage the same way, from the stored metadata: the
   relation's columns plus each join's `projects` (`bindings.translation_projects`, the one reading). The message
   names the view and what it projects.
4. Unchanged: a stage that reads its relation directly; an inferred stage (not judged by the gate); hashdiff
   attributes (`W_ATTR_NOT_IN_SOURCE`).

## 3 Not done

- The column a join reads on the relation's side (`COMPONENTID`) is not checked here: it comes from a ratified
  foreign key of that relation, and `expected_source_columns` carries it.
- No remedy text on the gate. With WP131 the known cause is repaired; the message names the missing column and the
  view.
- **A binding ratified at sign-off is not re-validated** (found by the replay, see §5) — candidate C70, not built.

## 4 Pre-registration

- **P1** guards (`tests/test_wp132_translation_stage_column_gate.py`) red first, then green. WP73's own guard
  pinned the skip (`stg_translated`, a translated stage reading a column nobody carries, not refused): it is
  updated in the fix commit, deliberately — the stage's view now projects the column it reads.
- **P2** suite with no key reachable, ruff, bare mypy.
- **P3** zero-cost replay of the demo's five stored runs with this WP alone (without WP131): the bill of
  materials' binding is refused in steps 3–5 and nothing else changes — no translated stage that built is refused.
- **P4** live: the demo's next chain raises no `BINDING_REJECTED` and no `E_STAGE_COLUMN_NOT_IN_SOURCE` on a stage
  that then builds (recorded in `docs/log.md`).
