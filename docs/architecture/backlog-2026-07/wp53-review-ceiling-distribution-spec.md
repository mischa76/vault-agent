---
type: spec
status: not-measured
updated: 2026-10-07
---

# WP53 — The review ceiling becomes a distribution

Status: **Approved and in progress** (2026-10-07, user: „ok, stell die Review-Decke auf eine
Verteilung um“) · Owner: Mischa Eismann · Author: Claude. Touches `eval/wp34_check.py` only (the
WP34 §6 review clause, re-based on decisions on 2026-10-05). No pipeline change; no model call.

## 1 Problem, measured

The review clause of WP34 §6 is a ceiling of **148 decisions** — the number of one chain, the
first that carried decisions (`20261004T013339024833Z`). Six normal chains since then: 148, 135,
142, 138, 139, 156 (`docs/log.md` 2026-10-04 → 2026-10-06; recomputed from the result files, not
from prose). The sixth failed the clause by 8 on modeler volume alone — a larger production model —
with every gate green. A single chain's number cannot tell a rise from the modeler's ordinary
spread, which is the thing the clause exists to tell; `eval/wp34_check.py` says it itself:
„a criterion carrying a guessed constant judges nothing“. The checker also tells the author not to
move a bar on a failing conjunction; this one is moved by the owner's decision, recorded above,
and its new form is not a number but a rule for computing one.

## 2 The rule

**A chain's decisions are judged against the distribution of the recorded chains before it.**

1. `REVIEW_DECISION_SAMPLES` records every completed normal chain of `adventureworks_incremental`
   that carries `review_decisions`, as (stamp, decisions), recomputed from the result files. A
   chain enters the record in the docs commit of its run, whether or not it met the clause — the
   record measures the modeler's spread, not the chains the clause liked.
2. The ceiling is the **one-sided 95 % prediction bound** for the next chain:
   `mean + t(0.95, n−1) · sd · sqrt(1 + 1/n)` over the samples (Student's t, sample sd). With
   fewer than 3 samples the clause cannot be judged and fails, saying so.
3. The judged run's own stamp is excluded from the samples, so re-checking an archived chain
   judges it against its predecessors only, never against itself.
4. The report line names the ceiling, the statistic, the sample count, mean, sd and date range,
   and says whether the run was excluded.

Under this rule the sixth chain (156) is judged against five predecessors (mean 140.4, sd 4.9):
ceiling ≈ 151.9 — **it still fails**, and the spec says so before the change: 156 is the highest
count recorded and lies outside the predecessors' spread. The seventh chain's ceiling, over all
six, is ≈ 159.9.

## 3 Guards before the change

1. `review_ceiling` reproduces 151.9 over the first five chains and 159.9 over all six (± 0.1).
2. A result carrying the sixth chain's stamp and 156 decisions fails the review clause against
   „5 recorded chain(s)“ with the run excluded; the same count without a stamp (a seventh chain)
   holds against six.
3. With two samples the clause fails with „cannot be judged“.
4. Every recorded sample matches its result file on disk when the file is present (the code
   owns every count).

## 4 Pre-registration

The seventh chain is judged against ceiling ≈ 159.9. If it exceeds it, that is a rise outside
six chains' spread and a finding; the bar is not moved again by hand.

## 5 Not in this WP

The other three clauses; the arm comparison's own review axis (arm A has one decision count,
134, and no distribution yet).

## 6 Results

*(appended after the change)*
