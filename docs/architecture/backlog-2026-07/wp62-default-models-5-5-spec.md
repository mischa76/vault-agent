---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP62 — The default models are Sonnet 5.5 and Opus 5.5

Status: **Approved and in progress** (2026-10-09, user: „ich sehe keinen grund wieso wir noch auf
den alten Modellen bleiben sollten. Es ist schneller, zuverlässiger und unterm Strich sogar noch
günstiger“) · Owner: Mischa Eismann · Author: Claude. Configuration defaults, the review record
per model generation, documentation. No pipeline logic changes.

## 1 Basis, measured

WP59 (`docs/log.md` 2026-10-09): one chain on Sonnet 5.5 / Opus 5.5 — all five steps green, 22.6
min against 45–55, 4.91 USD against 6.4–7.7, zero backstop fires, zero satellite-less hubs; the
review clause failed on a Sonnet 5.5 output defect WP61 repairs (unmeasured live); the ledger
matrix on Opus 5.5: the CDK line still needed (keep), the effectivity line a candidate-delete the
owner keeps. The 5.5 models refuse forced tool use; WP60's auto mode held on 0 of 114 calls
without a tool block. The owner's reading: faster, more reliable, cheaper — no reason to stay.

## 2 The rule

1. `Settings.primary_model = "claude-sonnet-5-5"`, `heavy_model = "claude-opus-5-5"`,
   `forced_tool_choice = False` (the mode the defaults need); `.env.example` and the
   configuration chapter say so. `FORCED_TOOL_CHOICE=true` with 4.x models remains a valid
   configuration (the forced request is byte-identical).
2. **The review record is per modeler model.** `REVIEW_DECISION_SAMPLES` becomes a mapping from
   `heavy_model` to its recorded chains; the checker reads the result's `models.heavy_model`
   (absent → `claude-opus-4-8`, the record every archived chain belongs to). The 4.8 record keeps
   its eleven chains; the 5.5 record **starts empty** — the twelfth chain's 238 carried the
   WP61 defect and would seed the distribution with it — and the clause reports „cannot be
   judged“ until three 5.5 chains are recorded (WP53 §2.2). A chain enters its model's record in
   the docs commit of its run, as before.
3. The ledger's header notes the defaults; the rows' „model last tested“ stay as measured.
4. Cost records: the 5.5 prices (WP59 §1) are the rates for every run from here; the 4.x rates
   stay in the log for the archive.

## 3 Guards before the change

1. `Settings()` with no environment gives the 5.5 models and `forced_tool_choice False`.
2. `check()` judges a result by its heavy model: a result naming `claude-opus-4-8` is judged
   against the eleven-chain record; one naming `claude-opus-5-5` reports „cannot be judged“
   with 0 recorded chains; one naming no model is judged as 4.8.
3. The WP53 guards still pass against the 4.8 record.

## 4 Pre-registration (the thirteenth chain, the first under the defaults)

All five steps green; `undetermined_type` decisions ≤ 3 (WP61 live — the twelfth had 158);
decisions reported, not judged (the 5.5 record has one entry after it); zero or near-zero
backstop fires; cost ≤ 5.5 USD; wall ≤ 30 min; WP57 carry-over ≥ 90 %.

## 5 Not in this WP

Re-measuring the remaining steering rules (no backstop) on 5.5; the Bedrock/Vertex routes.

## 6 Results

*(appended after the change)*

**2026-10-09 — built, keyless.** Guards `f5b87ac` (failing), the change in the commit carrying this
line: the defaults, `.env.example`, the per-model review record (`REVIEW_DECISION_SAMPLES` keyed by
`heavy_model`, `DEFAULT_RECORD_MODEL` for archived results), the WP53 and WP60 guards re-based
deliberately, the configuration chapter, changelog, ledger header, CLAUDE.md. Full suite, ruff,
mypy. §4 is **not yet measured** — the thirteenth chain, next.
