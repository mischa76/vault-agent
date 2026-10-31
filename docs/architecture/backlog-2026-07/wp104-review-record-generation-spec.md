---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP104 — The review record is per product generation

Status: **Approved and in progress** (2026-10-31, the owner's go to continue the plan of 2026-10-30, whose
third point this is) · Owner: Mischa Eismann · Author: Claude. Eval instrument only (`eval/wp34_check.py`);
no pipeline, gate, prompt or fixture changes.

## 1 What is wrong, in one paragraph

The review clause of WP34 §6 judges a chain's review decisions against the chains before it: a distribution
since WP53 (2026-10-07), a record per modeler model since WP62 (2026-10-09), with a floor since WP70. The
5.5 record's seven chains (2026-10-09 → 2026-10-17, 84–88, mean 84.7) all ran before WP79. The twenty-second
chain — the C1 experiment's control arm, 2026-10-30 — ran under WP79–WP99 and carried decision classes the
record had never seen: `link_binding_evidence` 8 (WP90, 2026-10-24: one decision per link staging bound by
evidence, in place of the ambiguous binding flag), `link_translation` 4 (WP40's licences resolving by
translation, now put in front of a reviewer); `source_binding` fell 8 → 2. Net +4: 91 against the ceiling
89.7, the first 5.5 chain to fail the clause, cause split against the twenty-first and recorded
(`docs/log.md` 2026-10-30). The clause exists to catch the modeler's drift. Judged against a record that
predates the product's own decision classes, it reports a product choice as a regression — and every next
chain at the new level would fail the same way, entering the record one „failure" at a time until the mean
caught up. That is the instrument measuring itself, not the modeler.

## 2 The rules

1. **The record stays per modeler model (WP62) and is split, within a model, into product generations.**
   `REVIEW_GENERATIONS` maps a modeler model to its generation boundaries, ascending: `(since_stamp,
   label)`. A model without an entry has one generation (the 4.8 record). The samples
   (`REVIEW_DECISION_SAMPLES`) are **not pruned**: every recorded chain stays recorded with its count and its
   stamp, and a generation is read from the stamps.
2. **A result's generation is the last boundary whose `since` is ≤ its own stamp**; a result without a stamp
   (a chain not yet recorded) belongs to the latest generation. It is judged against the samples of its own
   generation that precede it (WP53: its own stamp and later ones excluded). The clause reports „cannot be
   judged" until `MIN_REVIEW_SAMPLES` (3) chains of that generation are recorded — WP53 §2.2, and the
   precedent of WP62 §2.2, whose 5.5 record started empty for the same reason.
3. **The 5.5 record's second generation begins at the twenty-second chain** (`20261030T184653194084Z`,
   WP79–WP99); its first sample is the twenty-second's 91. The first generation (WP62–WP78) closes with the
   twenty-first: seven chains. A chain stamped after the twenty-first and before the twenty-second would
   still be in the first generation; none exists.
4. **A generation boundary is a product boundary, drawn once, with the cause split written down before the
   boundary is drawn** — here the split of 2026-10-30 — never because a chain merely came out high. Drift
   inside a generation remains what the clause catches; a chain that rises for a reason nobody has split
   fails and enters the record, as the sixth and the twenty-second did.
5. **The report line names the generation** when the model has more than one.
6. **No archived judgement of the first generation changes**: the seventeenth is still judged against 88.3,
   the eighteenth against 88.2, the twentieth against 88.6, the twenty-first against 89.3. The
   twenty-second's answer changes from „FAILED 91 > 89.7" to „cannot be judged: 0 chains of its generation
   before it" — its 91 is the generation's seed, and the finding stays where it is recorded, the log of
   2026-10-30.

## 3 Not this WP

- A per-kind record (decisions per flag kind), which would let a chain be judged on the kinds the record
  knows and leave the new ones out — more instrument than eight 5.5 samples justify; open as the next step if
  the product keeps adding decision kinds.
- The `project_self_contained` discrepancy WP101 recorded (the kept chains' 1.0 would not all hold
  re-scored): a per-step scorer, not a distribution — nothing in the record to re-base; the log entry is the
  record.
- The tolerance (WP70, the owner's number) and the other three clauses.
- The arm comparison; the drafted arm (`adventureworks_drafted_incremental`) is not a normal chain and enters
  no record.

## 4 Acceptance (keyless)

1. The twenty-second chain's archived result, re-checked, reports „cannot be judged" with 0 recorded chains
   of its generation, and the generation's label (P1).
2. A 5.5 chain without a stamp is judged against the second generation: „cannot be judged, 1 recorded
   chain(s), need 3" (P2).
3. The four first-generation judgements of rule 6 are unchanged, pinned with synthetic results at the archived
   stamps and counts; a result stamped between the twenty-first and the twenty-second is judged against all
   seven (P3).
4. The 4.8 record is untouched: eleven chains, one generation, no label in the line (P4).
5. `uv run pytest`, `uv run ruff check`, bare `uv run mypy`; the existing guards of WP53, WP62 and WP70 pass
   as written, except WP70's report-line fixture, whose synthetic 5.5 record predates the generation table
   and gets it emptied — deliberately, in the same commit, reason in the message (P5).

## 5 Pre-registration (keyless)

- **P1** (archived twenty-second, local file): clause line contains `cannot be judged`, `0 recorded
  chain(s)`, and the label; the clause fails, so the chain's conjunction fails — as the thirteenth's did
  under WP62.
- **P2** (unstamped 5.5): `1 recorded chain(s), need 3`.
- **P3** (synthetic, archived stamps): seventeenth 83 → HELD, `88.3`, 3 chains; eighteenth 85 → HELD,
  `88.2`, 4; twentieth 88 → HELD, `88.6`, 5; twenty-first 87 → HELD, `89.3`, 6; a chain stamped
  `20261020T000000000000Z` with 91 → FAILED against `89.7` over 7.
- **P4** (4.8): `_chain()` unstamped → HELD, `11 recorded chain(s)`, no `generation` in the line.
- Falsified if any P3 number moves: then the generation lookup changed an old judgement, and the change is
  wrong.
