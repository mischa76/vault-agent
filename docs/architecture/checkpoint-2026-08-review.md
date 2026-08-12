---
type: review
status: advisory
reviews: checkpoint-2026-08-proposal.md
---

# Review of the Checkpoint 2026-08 proposal

Written 2026-08-12 (Claude Opus 5), at Mischa's request, on
`checkpoint-2026-08-proposal.md` (Fable, same day). A separate document rather than an appended
section: records under `docs/architecture/` are append-only and the proposal is another author's
text, so this comments beside it instead of inside it.

**Recommendation: ratify, with three changes.** The document does the thing that matters — it
corrects an *instrument* with reasoning written down first, rather than lowering a bar because a
run came out badly. `.claude/rules/eval.md` forbids the second and permits the first, and Part A
is squarely the first: the ≥8 clause was set against a supply of 16 that counted 18 foreign keys
which graph order put permanently out of the proposer's reach. That is a miscounted denominator,
not a disappointing result.

Endorsed without change: dropping the review-load clause from judgement at n=1 (the 546-vs-833
pair on identical inputs is direct evidence), naming a project-level clean state at all, and the
five-criterion structure.

## 1. The re-derived link clause is calibrated to pass

Part A proposes ≥4 applied cross-domain links against an offline prediction of ~5. A bar the
change is already computed to clear cannot fail except through an unrelated regression. That is
a useful floor and a poor test, and it is the mirror image of the failure §6 was shaped to avoid:
WP30.3 met a bar it had written in advance while regressing elsewhere.

**Proposed instead:** the run is judged on whether it MATCHES the offline prediction —
9 proposals, `ambiguous_hub` 7, `no_hub_for_key` 22, 5 proposals finding a near hub, ~5 applied
cross-domain links — within a tolerance stated before the run. Deviation in *either* direction is
the finding: 9 links would mean the pipeline is understood no better than 2 would. Keep ≥4 as a
floor beneath it.

This tests what is actually at stake after 2026-08-12: whether offline reasoning against recorded
shapes can replace paid runs. Two findings that day were free and each superseded a planned run.
If the prediction holds, that method is evidenced rather than asserted.

## 2. §6's invention clause was half-implemented, and it failed silently in both runs

The spec (§6, second bullet): *"Zero-satellite hubs must not rise above the WP30.2 baseline, and
`hub_sales_representative` must not return. This is the clause WP30.3 failed."*

The named half was **absent from `eval/wp34_check.py` entirely** — the string appears nowhere in
the file. And `hub_sales_representative` is present in the final model of **both** 2026-08-12
runs. Both were therefore reported against a clause that was never computed, including in this
reviewer's own summary after the first run, which stated the hub had not returned. That claim
was read out of the checker's silence, and the silence meant nothing.

This matters beyond one hub. The checker's stated value is its commit date — "a criterion
evaluated by hand after the numbers arrive explains anything" (log, 2026-08-11). A
pre-registered criterion that is not implemented is weaker than one evaluated by hand, because
it looks like it was checked.

**Implemented 2026-08-12** as part of this review, deliberately as an implementation of what §6
already required and not a re-derivation: nothing is loosened, a clause that was always in the
pre-registration simply started being computed. Validated against the four archived 2026-08-09
chains, where it reproduces the historical record exactly — absent in the WP30.2 baseline
(review 619), present in WP30.3 (review 777), which is the run the log says failed on it.

The named check is stricter than the count on purpose: the hub can return *carrying a
satellite*, which the zero-satellite count would not notice.

**Consequence for the checkpoint:** completing the checker belongs before the run, not after.
Any other clause in a pre-registration should be re-read against its implementation at the same
time — this one was not caught by review, but by looking for something else.

## 3. A missing criterion: the binder fix is unverified against a real warehouse

`cb01b9c` changes construct↔relation binding for 53 of the 68 declared tables in the corpus.
Generated staging now reads the declared table where it previously fell back to a `raw_*`
relation that does not exist. That should be strictly better — and untested is untested. The
last PostgreSQL verification predates the change.

The proposal's "What the checkpoint claims when green" states *"Greenfield end-to-end:
live-verified"*. With this change unexercised against a real warehouse, that sentence is no
longer covered by its evidence, which is precisely the footnote the checkpoint exists to avoid.

**Proposed criterion 6:** one grounded demo run against real PostgreSQL, judged by the dbt build
succeeding and staging binding to declared relations rather than `raw_*`. Cost is the demo's
normal cost, not a new eval run.

## 4. Two smaller notes

**The cost column conflates money with effort.** Criterion 2 (WP29 §4 unblocked) is "0" in the
sense of no API spend, but it is real engineering — `dataset.yml`, requirements, scorer dispatch
and a scorer key-shape fix. A reader planning a week from this table would under-plan it. Suggest
splitting into *spend* and *effort*.

**The review-load axis is the charter claim, not one axis among several.** Removing it from
judgement at n=1 is right; leaving it unscheduled is not, because the charter claim then never
gets tested. Suggest recording it as a named debt with its price: n≥3 per arm, ~$27, after the
deterministic defects are exhausted — and noting that every arm-B number before `cb01b9c` is void
regardless of n.

## Summary

| # | Change | Kind |
|---|---|---|
| 1 | Judge the run against the offline prediction; keep ≥4 as a floor | strengthens Part A |
| 2 | Complete `wp34_check`'s invention clause before the run (done 2026-08-12) | fixes a pre-registration |
| 3 | Add a grounded PostgreSQL criterion for the binder fix | closes a scope gap |
| 4 | Split spend from effort; schedule the charter-claim measurement as priced debt | clarity |

Nothing here changes Part B's structure or the fork it defers. The decision remains Mischa's.
