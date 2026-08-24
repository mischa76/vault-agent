# WP30 arm-B rerun protocol — written before the run

**Date:** 2026-08-14 · **Status:** Proposed, blocked on ADR-0013 · **Spec:** wp30 §7.3, wp34 §6

## Why a rerun, restated once

Every arm-B (incremental) measurement ran with a binder that could not match a multi-word
CamelCase table (53 of 68 on AdventureWorks) — exactly the near-side lookup incremental runs
depend on. Fixed 2026-08-12 (`cb01b9c`). The 73%-link-deficit and 3x-review-item findings are
therefore CONTAMINATED and uncitable until the comparison is repeated (spec §7.3). Arm A
(greenfield, one pass) did not depend on the binder and its numbers stand as baseline.

## Step 0 — decide what is being measured (blocked on ADR-0013)

Two legitimate experiments; pick one *before* paying:

- **ADR-0013 accepted and built:** the rerun measures the full mechanism (binder fix +
  surrogate→NBK translation). Pre-registered prediction: ~5 + 4 = ~9 cross-domain links against
  wp34 §6's bar of 8.
- **ADR-0013 rejected/deferred:** the rerun measures the binder fix alone. Prediction: ~5 links,
  §6's link clause fails by construction — then the honest outcome is revising the bar with the
  18-structural/4-design split as the argument, not calling the mechanism broken.

Either way the choice is recorded here before the run, so the result is a finding and not an
explanation.

## Step 1 — trace audit, zero cost [do first, regardless of step 0]

Per the invariant (audit traces before paying): the two 2026-08-12 WP34 runs already exercised
the fixed binder on the incremental path. Before any new spend, extract from
`.vault-agent/traces/*.jsonl` and `eval/results/`:

1. Which of the ~5 predicted post-fix links actually landed per increment, by name.
2. Review-item counts per increment from those runs — if they already answer the direction of
   the review-load axis, say so; the paid rerun then only confirms.
3. Zero-satellite-hub counts vs. the WP30.2 baseline (invention clause), now that the clause's
   half-implementation is fixed (log 2026-08-12).

If the audit already answers §6's conjunction in the negative, stop: no rerun money until
ADR-0013 changes the mechanism.

## Step 2 — the paid rerun

- **Cases:** `adventureworks_incremental` (the five areas sequentially into the arm-A vault),
  1 repeat, same seeds/config as the contaminated run except the binder fix (+ ADR-0013 build,
  per step 0).
- **Budget expectation:** the five greenfield areas cost $11.97 (spec §7.3); incremental arm
  with existing-vault context ran comparably before. Cap at **$20**; abort and audit if any
  increment exceeds 2x its arm-A sibling.
- **Measure, against wp34 §6's conjunction (all four clauses):** cross-domain links (bar 8);
  zero-satellite hubs vs. WP30.2 baseline; review items vs. the 619 baseline (must fall);
  zero wrong joins (deterministic staging check). Plus the §7.3 comparison axes against arm A.
- **n=1 discipline:** one repeat is a direction, not a verdict — the contaminated comparison
  earned exactly that caveat and it applies to the repaired one too. If the direction is
  surprising, the second repeat comes before the narrative does.

## Step 3 — close out

Log entry with the numbers and the §6 verdict; update wp30 §7.3's CONTAMINATED marker to point
at the rerun entry (new dated text, never editing the old); if §6 fails with the capability
built, the falsification clause applies — revise the charter claim, no fifth intervention.
