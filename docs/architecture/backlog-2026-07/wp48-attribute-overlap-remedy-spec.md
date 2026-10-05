---
type: spec
status: not-measured
updated: 2026-10-05
---

# WP48 — A remedy with memory for `E_SAT_ATTR_OVERLAP`

Status: **Approved and in progress** (2026-10-05, user: „ok, dann bau die Remedy mit Gedächtnis für
E_SAT_ATTR_OVERLAP") · Owner: Mischa Eismann · Author: Claude. Touches the gate (WP20, ADR-0012),
the repair memory (WP44, WP46), the modeler's `drop_retired`. No prompt change; no model call.

## 1 Problem, measured

In the cumulative chain `20261005T092147230544Z` (`docs/log.md` 2026-10-05) step 2's modeler built
`sat_employee_profile` and `sat_employee_demographics`, both from `Employee`, both carrying
`MaritalStatus`. `E_SAT_ATTR_OVERLAP` fired, correctly; the diagnosis carried no typed remedy;
three attempts did not repair it; the eval accepted the red model unattended; steps 3, 4 and 5
inherited the two satellites and, under the additivity rule, could not change them — four red
steps from one modeler mistake, and no mapper in any of them. The collision had the same
history until WP44 (2026-09-13 → 2026-10-04). The rule can say which satellite keeps the
attribute; nothing said it.

## 2 The rule

**The gate says which satellite keeps the attribute, and the loop keeps it said.**

`rules.satellite_attribute_remedy(satellites, attribute, existing)` decides, in order:

1. Every owner is in the existing vault: **inherited** — nothing this increment emits can remove
   it; the remedy says so and retires nothing (as the collision remedy does).
2. Exactly one owner is in the existing vault: it keeps the attribute (an existing satellite is
   immutable); every new owner drops it.
3. Among new owners, the first by name keeps it; the text says the choice was arbitrary and
   that a human may move it at the checkpoint. A declared relation does not break the tie:
   under ADR-0012 the error only fires when all owners draw from the same relation, so it
   declares the column for all of them alike.

The issue carries the remedy text and `retires_attributes` — `(satellite, attribute)` for every
owner that drops it. The validator records each as a `RetiredConstruct` of kind `attribute`
(`name` the satellite, `attribute` the label). The modeler's `drop_retired` removes a retired
attribute from a re-emitted satellite of that name — the satellite stays, only the column goes
— with one `retired_reemitted` flag (a disclosure: nothing is lost, the attribute lives in the
keeping satellite) and one backstop event. A satellite re-emitted without the attribute passes.

Branching is on the attribute's normalised identifier and the satellites' names, never on text.

## 3 Guards before the change

1. The remedy: rules 1–3 on three shapes; the inherited pair retires nothing.
2. The validator: the issue carries the remedy and the retirements; `state.retired_constructs`
   gains one `attribute` entry per dropping satellite; an inherited pair adds none.
3. The modeler: with `(sat_employee_profile, MaritalStatus)` retired, the real step-2 shape
   (fixture cut from the run's persisted model) comes back without `MaritalStatus` on the
   profile satellite, with it on the demographics one, one `retired_reemitted` flag and one
   backstop event; validated afterwards, no `E_SAT_ATTR_OVERLAP`.
4. Inert: a model with no retirement passes through unchanged; a satellite re-emitted without
   the attribute raises nothing.

## 4 Pre-registration

Replayed on the cumulative run's step-2 model: the remedy keeps `MaritalStatus` on
`sat_employee_demographics` (first by name among two new owners) and retires it on
`sat_employee_profile`; the repaired model raises no overlap. On the next chain, if a step's
modeler duplicates an attribute within one relation again: the gate fires once, the remedy is
followed or the memory enforces it on the next attempt, the step is green on that class, and no
later step inherits it. `validation_gate` otherwise unchanged. Not predicted: whether the
modeler produces the shape at all (two of four October chains did not).

## 5 Not in this WP

- Reporting an *inherited* error as inherited so a clean delta can be green: a validator
  decision for the owner (the collision's inherited case has the same shape).
- Running the mapper's deterministic re-bind on the failed path (`docs/log.md` 2026-10-05).

## 6 Results

*(appended after the change)*

**2026-10-05 — built, keyless.** Commits `7552935` (guards, failing) and the change commit
after it. `satellite_attribute_remedy`, `ValidationIssue.retires_attributes`,
`RetiredConstruct` kind `attribute`, `drop_retired` on attributes. Guards 1–4 pass; replayed on
the cumulative run's step-2 shape: `MaritalStatus` stays on `sat_employee_demographics`, leaves
`sat_employee_profile`, no overlap afterwards. §4's chain half is **not yet measured live**.
