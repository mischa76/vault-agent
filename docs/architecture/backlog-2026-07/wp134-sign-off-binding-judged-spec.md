---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP134 — A binding made at sign-off is judged by the gates that read a stage's relation (C70)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C70 and C71) · Owner: Mischa
Eismann · Author: Claude. Candidate C70.

## 1 What is wrong

Two gates judge a stage by the relation it reads: the column gate (`E_STAGE_COLUMN_NOT_IN_SOURCE`, WP73, WP132)
and the satellite grain gate (`E_SAT_GRAIN_NOT_UNIQUE`, WP85, WP133). Both run in the validator, before the
sign-off. A stage no rule could bind is unbound when they run; a human binds it at sign-off (WP82), staging is
re-bound, and nothing validates again. What the sign-off does check (`bindings.check_stage_bindings`) is its own,
second reading of the stage's metadata, and it has drifted from the validator's twice:

1. **It does not look at grain.** The demo's first chain (2026-11-15) bound `stg_work_order_operation` to
   `WorkOrderRouting` at sign-off. Replayed with that binding known, the validator refuses
   `sat_work_order_operation_details`: the relation is unique on WorkOrderID + ProductID + OperationSequence, the
   satellite's key covers two of them. The live run never said so. In AdventureWorks' data the two columns happen
   to be unique; on other data the satellite re-inserts on every load, unseen (WP132 §5, C70).
2. **It still judges a translated stage the way WP132 stopped doing.** A stage that reads through a translation
   view hashes columns the view projects, not the relation. The sign-off check demands them from the relation:
   measured on the ten stored runs of 2026-11-15, it refuses the very binding each of the 213 translated stages
   already has (5, 6, 21, 27, 45 and 5, 7, 24, 30, 43 per step), and accepts the binding of point 1. No such stage
   was bound at a sign-off so far, so nobody met it.

## 2 The rules

1. **One reading for both places.** The grain judgement moves out of the validator into a function both call
   (`bindings.satellite_grain_gap`): a satellite's key columns, mapped back to the relation through derived
   columns, a binding's aliases and the translation's typed `reads`, against the relation's declared unique keys.
   The validator's gate keeps its code, severity, message and remedy to the letter.
2. **A sign-off binding that fails the grain judgement is refused**, like one that fails the column check: the
   message names the stage, the relation and its unique key, the satellite, the columns its key lacks, and the
   gate's code. The stage keeps its inferred relation and its review item. Exempt as in the gate: a satellite of
   the vault being extended, an effectivity satellite, a relation without a declared key, a stage whose stored
   translation carries no `reads`.
3. **What the relation of a translated stage must carry** is what the stage reads from it: its key columns less
   the ones the view projects, plus each join's referencing column (`reads`). The sign-off check and the list the
   checkpoint shows a human (`pending_stage_bindings`, `expected_columns`) use this reading; the projected
   columns are no longer asked of the relation.
4. Unchanged: the grammar and the three paths of WP82 (CLI, workbench, prompt); a binding that passes is applied
   as before; the validator's column gate (it does not check the referencing column — WP132 §3 — and still does
   not).

**Why refuse and not disclose** (the candidate's second option: apply the binding, re-validate, show the result
as a decision). The grain gate is a gate: bound when the validator runs, the same stage costs the modeler an
attempt and the satellite becomes multi-active. A binding at sign-off that leaves the state the gate refuses is
a way round a gate, and after the sign-off nobody is left to act on a decision — the run finishes. The human is
told before anything resumes and has two ways: leave the stage unbound and provide a relation unique on the
satellite's key (the view every inferred stage needs anyway), or run again with the satellite multi-active.

## 3 Not done

- **No second validator pass after a re-bind.** The two gates that read a stage's relation are run on the
  binding; the gates that read the model (keys, payload, optional participants) do not change with a binding.
- **The mapper's own re-bind** (a hub's stage bound by its mapping proposal after the validator) is not
  grain-judged either. Not observed as a defect: a hub's key is a declared key of its table. Left.
- The refusal is a message in the three paths. No typed error object: `_apply_binding_decision` reads the stage
  from the message's prefix, as before WP134 — noted, not changed.
- A binding to a relation that carries same-named columns of another meaning (the demo's `stg_product_subcategory`
  on `Product`, whose `Name` is the product's) passes both judgements. Names cannot tell; it stays the human's.

## 4 Pre-registration

- **P1** guards (`tests/test_wp134_sign_off_binding_judged.py`) red first — the seven that state the new behaviour;
  the five that pin what stays (a covering key, a multi-active satellite, a relation without keys, an existing
  satellite, an effectivity satellite) green by design — then all green.
- **P2** suite with no key reachable, ruff, bare mypy; the guards of WP82, WP85, WP130, WP132 and WP133 unchanged
  — the validator's messages are theirs to pin.
- **P3** zero-cost sweep over the ten stored runs of 2026-11-15 (`workbench/chain-20261115`, `…b`): the sign-off
  check asked about every binding each run ended with. Before: 213 refusals, all on translated stages, the
  binding of §1.1 accepted. After: no translated stage refused, and exactly one binding refused — the first
  chain's step 3, `stg_work_order_operation` → `WorkOrderRouting`, by the grain judgement.
- **P4** live: none planned. The refusal is deterministic and needs no model; a workbench run that meets it at a
  sign-off would be the live case.

## 5 Measured

Appended when built.

### Measured (2026-11-16)

- **P1 ✔.** Seven of twelve red at `4c2867c`, twelve green after.
- **P2 ✔.** Numbers in `docs/log.md`. The guards of WP82, WP85, WP130, WP132 and WP133 untouched and green; the
  validator's gate now calls `bindings.satellite_grain_gap` and its message is byte for byte what they pin.
- **P3 ✔ with a deviation.** Before (`4c2867c`): 213 refusals, all on translated stages, all for the keys their
  views project; the first chain's sign-off binding accepted. After: of those 213, 210 pass. **Four bindings
  are refused, not the one announced:** the first chain's step 3, `stg_work_order_operation` →
  `WorkOrderRouting`, by the grain judgement („unique on WorkOrderID + ProductID + OperationSequence, but
  sat_work_order_operation_details … covers only OPERATIONSEQUENCE, WORKORDERID") — the announced one; and the
  first chain's `stg_product_assembly_component` → `BillOfMaterials` in steps 3, 4 and 5, for `PRODUCTNUMBER`.
  That is C67's stage, the one the warehouse refused (WP131, WP132): its assembly key was hashed from a column
  neither the relation nor the view carried. The sweep asks about the bindings the runs ended with, and that
  binding was wrong; the prediction forgot it. The second chain: 438 bindings over five steps, none refused (the first: 358). In
  steps 4 and 5 of the first chain the work-order stage is not refused: its satellite belongs to the vault being
  extended there, exempt as in the gate.
- **P4** not measured: no sign-off has met the refusal live.
- **Not announced, done:** the validator's helper for the names of the vault being extended moved to
  `existing_model.existing_construct_names`, so that the sign-off's exemption reads the same set.
