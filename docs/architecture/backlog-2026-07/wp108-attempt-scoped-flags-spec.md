---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP108 — The code generator and the model merger re-derive their flags on every run (C8)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C8 is from the owner's own build (2026-10-20 → 22): flags raised for a construct in one modeler
attempt survived a re-model whose final shape no longer earned them, and the sign-off asked about them.

## 1 What is wrong, measured on the kept chains before the change

The re-model loop (`route_after_validation`) runs the modeler, the merger and the code generator again per
attempt; each run *appends* its flags (`dedupe_flags` removes identical copies, nothing else). A generator flag
describes the model the generator was given; after a re-model that model is gone, the flag stays. Read on the
three kept chains of 2026-10-30/31 (the twenty-third, arms A and T; two modeler attempts per step, one step with
three): today's generator replayed on each step's **final** model raises **none** of the 19 recorded generator flags
of the kinds `generation_gap`, `column_collision`, `missing_input` — **19 of 19 are stale** (twenty-third: 3, 1, 0,
2, 1 = 7; arm A: 6; arm T: 6), every one a `generation_gap` from the first attempt (a multi-active satellite on a
multi-source hub without its feed, a satellite declaring a `source_table` that is no feed of its parent), repaired
in the second attempt and still in the review as a **decision** — 7 of the twenty-third's 95. The merger's three
recorded `extension_conflict` flags are current: the restated link is in the last attempt's delta each time (the
traces' `emit_dv_model` payloads), so re-deriving them changes nothing there.

## 2 The rules

1. **The generator's flags are the final attempt's.** `CodeGeneratorAgent.run` first drops every flag whose
   `agent` is `code_generator` — its own, staging's (`build_staging`, re-raised in the same run and replaced again by
   the mapper's re-bind, WP75), the zero-key hubs' and the Business Vault's (both raised under the generator's name
   inside its run) — and then raises this run's. Nothing another agent raised is touched.
2. **The merger's conflicts are this delta's.** `merge_models` first drops every flag whose `agent` is
   `model_merger`, then flags what this delta re-states. A restatement the last attempt repeats is flagged again
   (the three recorded ones would be); one it repaired is not.
3. **The modeler's own flags stay as they are — deliberately.** `retired_*` (WP44–WP52) and `dropped_record` record
   what the repair memory and the parser did to an attempt's output; WP57 carries the *repaired* previous model into
   the next attempt, so the orphaned payload or the dropped record is not re-emitted and could not be re-flagged. A
   `retired_orphan` decision from attempt 1 is still the human's to answer after attempt 2. Those flags are not
   derivable from the final model, so they are not re-derived.

## 3 Not this WP

Scoping the modeler's flags (rule 3 says why). The eval's review record: the next chains will carry fewer
decisions by this class (the twenty-third: 7 of 95); WP34 §6's record is appended with that note, no sample moves.

## 4 Acceptance (keyless)

`tests/test_wp108_attempt_scoped_flags.py`, committed red (two of four; the two pins green): the generator run on
an attempt-1 model (a link naming a hub it did not build) flags the gap, and run again on the repaired model leaves no
gap and generates the link; the flags of the parser, the modeler (`retired_orphan`) and the proposer survive both runs
unchanged; the merger flags a restated link and, after a clean delta, holds no conflict; a restatement the last delta
repeats stays flagged.

## 5 Pre-registration (keyless)

- **P1** The twenty-third chain's first-attempt models reconstructed from the trace (`emit_dv_model` payload 1 of each
  step, merged onto the kept previous step with `merge_models`, no further appliers) and run through today's generator
  raise the recorded stale flags by (kind, asset): **3, 1, 0, 2, 1 — 7 of 7**; arms A and T likewise, 6 and 6 (arm T's
  three-attempt step: the union of attempts 1 and 2). The same states run through the generator a second time on the
  final model carry **0** of those 19 after the change, and exactly the final model's generator flags (0 of these kinds).
  Any stale flag the reconstruction does not reproduce is reported with its reason (an applier the reconstruction skips).
- **P2** The three recorded merger flags re-derived from the last attempt's delta: raised again, 3 of 3 — current.
- **P3** Suite green, ruff, bare mypy; WP75's re-bind guards and WP43's review-queue guards unchanged.

## 6 Measured

Appended after the run.
