---
type: spec
status: not-measured
updated: 2026-10-12
---

# WP70 — The review ceiling gets a floor: mean plus a tolerance of five decisions

Status: **Approved and in progress** (2026-10-12, user: „go, bau WP70 mit der Toleranz von
fünf“, after the question what `MIN_REVIEW_SAMPLES` rested on) · Owner: Mischa Eismann · Author:
Claude. Changes WP53's rule, not its record; WP34 §6's review clause keeps its letter — a chain
is judged against the chains before it — and gains a floor. No agent, gate or prompt changes.

## 1 The finding

WP53's ceiling is the one-sided 95 % prediction bound, mean + t(0.95, n−1) · sd · √(1 + 1/n).
It needs a spread to describe. The 4.x record had one (126–156 over eleven chains; the bound
sat 16–22 decisions above the mean and settled after the sixth chain). The 5.5 record does not:
84, 83, 83, 83 — sd 0.5, bound 84.6, one decision above the mean. That bound no longer predicts
a next chain; it demands the next chain equal the last four. A fifth chain at 86 would fail it
and then lift it to 86.8 — the clause would be answering noise with noise.

## 2 The rule

1. `REVIEW_TOLERANCE = 5` decisions. The ceiling is **max(t-bound, mean + REVIEW_TOLERANCE)**.
   With a wide record the t-bound wins and nothing changes (every 4.x verdict is reproduced);
   with a tight record the floor holds the bar at a distance a human can call spread.
2. Five is the owner's number: about 6 % of the 5.5 mean, well under the 12–15 % the 4.x
   bound carried, so a real rise (the sixth chain's 156 against 140, +11 %) is still a finding.
3. The report line names which of the two applied, so a verdict can be read without
   recomputing: „floor mean + 5“ or „t-bound“.
4. `MIN_REVIEW_SAMPLES` stays 3: the floor needs only a mean, the t-bound still needs its three.

## 3 Guards before the change

1. `review_ceiling([84, 83, 83, 83])` is 88.2 (mean 83.25 + 5) and `review_ceiling` over the
   4.x record's first five stays 151.9 — the t-bound wins there, the floor never lowers a bar.
2. The clause's report line names the floor when it applied and the t-bound when it did.
3. The seventeenth chain's archived result, re-checked, holds against 88.3 (its three
   predecessors' mean 83.3 + 5), the line naming the floor.

## 4 Not in this WP

Re-telling any 4.x verdict (none changes); a tolerance relative to the mean (five is absolute,
by the owner); a change to the record.

## 5 Results

*(appended after the change)*

**2026-10-12 — built.** Guards `32111a1` (red), the change and these lines in the commit
carrying them. `review_bounds` returns both candidates, `review_ceiling` the larger,
`REVIEW_TOLERANCE = 5`; the clause's line names „the floor mean + 5 (WP70; t-bound …)“ or „the
one-sided 95 % prediction t-bound (floor mean + 5: …)“. **Re-checked:** the seventeenth chain
holds against 88.3 (floor; t-bound 85.3); the sixth chain still fails against 151.9 (t-bound;
floor 145.4) — no 4.x verdict moved; the sixteenth is still „cannot be judged“ (two
predecessors). The eighteenth is judged against 88.2 (four samples, mean 83.25 + 5).
