# Scale-hardness test findings (WP13 / Charter A)

Status: **live half started — 30-table step run 2026-07-19 (gate failed on an eval-side
artifact, see Candidate #2); 100/300 not yet run** · Owner: Mischa Eismann · Spec:
`backlog-2026-07/wp13-scale-hardness-spec.md` · Charter:
`roadmap-2026-07-productization.md` §Charter A.

The tooling half (deterministic landscape generator, `scale_30/100/300` eval cases,
`ForcedToolCaller` usage capture) is merged and keyless-tested. This document is the
record of the **live measurement protocol** (spec §4): real LLM runs in the WSL
environment, one repeat per size step, escalating only while the previous step stayed
green and within budget.

## How to run it

```bash
# 0. (optional) eyeball a landscape before spending tokens — keyless, deterministic:
uv run python -m eval.scale.generate --tables 30 --seed 42 --out /tmp/scale30

# 1. the committed 30-table step (gated: mapping_accuracy >= 0.8, pipeline_health = 1.0):
uv run python -m eval.run --dataset scale_30

# 2. escalate ONLY while the previous step completed and stayed in budget:
uv run python -m eval.run --dataset scale_100     # synthesised on demand (100 tables)
uv run python -m eval.run --dataset scale_300     # synthesised on demand (300 tables)
```

Each run writes one JSON per repeat under `eval/results/<case>/` (git-ignored) carrying
scores **and** the `metrics` block: `usage` (calls, input/output/cache-read tokens, by
model), `wall_clock_seconds`, `review_items_total`, `review_queue_lines`, construct
counts, flag count. The console prints a compact scores + usage/wall-clock/review summary.

Since WP15 each repeat also writes its **LLM transcript** next to the result JSON
(`<timestamp>-run<N>.trace.jsonl`, path echoed in `metrics.trace_path`): one JSON object per
API call/failure with the full system prompt (once per sha), user content, and the tool
payload the model returned.

> **Finding protocol (WP15 §2.4):** before filing a finding below, grep the trace for the call
> where the model's judgment diverged and cite its `tool_name` and `attempt` in the entry —
> findings quote transcripts, not hunches. E.g.
> `jq -c 'select(.tool_name=="emit_dv_model") | {attempt, payload}' eval/results/scale_30/*.trace.jsonl`.

### Budget & abort criteria (spec §4)

- One repeat per step; escalate 30 → 100 → 300 only while the previous step completed.
- **Set a cost ceiling before starting.** Estimate the next step's cost from the previous
  step's token totals (they scale super-linearly with table count) and stop if the
  projection exceeds the ceiling.
- Abort a step that hard-fails twice; record which agent and which limit it hit.
- Every breakpoint found becomes its **own** follow-up WP — this WP only *finds* them.

## Results

Fill one block per executed step. Copy the numbers from the run's console summary and the
result JSON `metrics`.

### Step: 30 tables (seed 42) — committed `scale_30`

Run: `uv run python -m eval.run --dataset scale_30` — **3 repeats** completed cleanly
(not 1; the default `--repeat` is 3). Values are mean over the 3 runs, with per-run
range where it varied.

| Measure | Value |
|---|---|
| Date / git SHA | 2026-07-19 / a04606d |
| Models (primary / heavy) | `claude-sonnet-4-6` (39 calls) / `claude-opus-4-8` (1 call — the modeler) |
| Wall-clock | mean **943.6 s** (~15.7 min); range 924.7–980.9 s. Total for 3 repeats ~47 min |
| LLM calls | 40 / repeat |
| Input tokens (cache-read share) | mean 64,508 / repeat; cache-read ~151–156k (≈239% of input — prompt caching effective) |
| Output tokens | mean 78,883 / repeat |
| Cost estimate | rough **≈ $1.5–2 / repeat**, ~$5 for 3 (output-bound: ~79k out vs ~65k in; recompute with live per-model pricing) |
| Hubs / links / satellites | 17 / 7 / **21–24** (sats varied: 24/24/21) |
| Validation verdict (+ issue counts) | **PASSED** all 3 (`validation_gate`=1.0, `pipeline_health`=1.0) |
| mapping_accuracy (vs sampled golden) | **0.069** all 3 — **GATE FAILED** (≥ 0.80). *Eval-side artifact, not a mapper regression — see Candidate #2* |
| gaps / unresolved | `gap_detection`=0.00 (0/3 golden gaps recalled — same concept-naming coupling, see Candidate #2) |
| Review items / rendered lines | mean 140 items (per-run **132 / 85 / 202** — high variance) / 54 rendered lines (53–56) |
| report.html size · Mermaid graph renders? | n/a — `eval.run` runs the graph in-memory (MemorySaver), writes no `report.html` to disk |
| First hard failure (agent / limit) | **none** — pipeline ran end-to-end; the gate miss is a *scored* result, not a crash |

Other observed scores: `driving_key_accuracy`=1.00, `confidence_calibration`=1.00,
`construct_f1`=0.00 (expected & ungated — `golden: {}` is empty; scale is a measurement
case, not a construct-regression gate).

Notes:
- **Non-determinism across identical inputs is high**: satellite count 21↔24 and flag
  count **77 ↔ 191** (review items 85 ↔ 202) over the 3 repeats. Worth watching as its own
  stability signal at larger N.
- Prompt caching is working well (cache-read ≈ 2.4× the fresh input tokens): the modeler's
  and enricher's stable system prefixes are being reused.

### Step: 100 tables (seed 42) — `scale_100`

**COMPLETED END TO END, 2026-07-29** (1 repeat) — the first time this case has ever finished.
An earlier attempt the same day reached the modeler but was killed by the operator's 50-minute
timeout; it is written up as Candidate #4 below, because what it measured is a finding in its
own right.

| scorer | score | reading |
|---|---|---|
| `pipeline_health` | 1.000 | no error flags |
| `validation_gate` | 1.000 | `passed=True`, 100 warnings within tolerance |
| `false_friend_hits` | 1.000 | 12 false-friend columns watched, none bound |
| `mapping_coverage` | 0.714 | 20/28 golden pairs — see the reading below, this is not a defect |
| `gap_detection` | 0.000 | concept-coupled, **reported only** in column mode (WP14) — blind by design at scale, not a quality signal |
| `construct_f1`, `driving_key_accuracy`, `existing_construct_preservation` | 1.000 | all **vacuous** — the synthetic case ships a golden mapping and no golden model |

Run: 137 calls, 463,951 in (cache-read 405%), 281,366 out, **818 s wall**, 68 hubs / 21 links /
35 satellites, 1,021 flags → 1,121 review items → 218 rendered lines.

**Peak output against cap — the table worth re-reading before the 300-table attempt:**

| agent | calls | peak out | cap | %cap | truncations |
|---|---|---|---|---|---|
| `emit_requirements` | 4 | 8,192 | 8,192 | **100%** | 2 → split, recovered |
| `emit_mapping` | 3 | 8,192 | 8,192 | **100%** | 1 → split, recovered |
| `emit_business_keys` | 1 | 7,444 | 8,192 | **91%** | 0 |
| `emit_contract_enrichment` | 129 | 5,381 | 8,192 | 66% | 0 |
| `emit_dv_model` | 1 | 13,261 | 32,768 | **40%** | 0 |

Three things this run establishes that were previously assumption:

1. **The modeler's 32,768 budget (WP22/ADR-0010) is right, and the extrapolation that chose it
   was accurate.** 13,261 actual against 13,889 predicted by isolated replay — the sub-linear
   growth model holds. ~60% headroom remains at 100 tables, so the ~26k estimate for 300 tables
   still fits. The transport ceiling is no longer the binding constraint.
2. **The source-mapper segmentation ran against the real API for the first time and worked.**
   It was keyless-tested only. The whole concept list truncated at 8,192, split, and both halves
   returned clean (4,790 + 3,939). Same for `emit_requirements`, which split twice.
3. **`emit_business_keys` made ONE call here and seven on the earlier attempt, from a
   byte-identical input.** At 91% of cap it sits on the boundary and sampling variance decides —
   the same flaky-breakpoint shape already recorded for the requirements parser. It recovers
   either way; the point is that a single green run is not evidence that it fits.

**Reading `mapping_coverage` 0.714 — the deferral is correct, the scorer conflates two things.**
All four missed pairs are the cross-system synonym trap class
(`CRM_PARTNER.EXTERNALPARTNERNO|VEKTRA_PARTNER.PARTN_NR` and the equivalents for contract,
policy, claim), and all four concepts are sitting in `unresolved` — `PARTN_NR`, `VERTR_NR`,
`POL_NR`, `SCHAD_NR`. That is precisely the behaviour WP9 specifies and documents: a business key
with candidates in two *different source systems* is never force-picked; it goes to the human with
both candidates and a WP10 multi-source pointer. The golden marks such a pair as *ambiguous*
(either candidate is acceptable); the mapper's correct answer is *neither, ask a human*. Those are
not the same thing, and `mapping_coverage` scores the second as a miss.

This is the **fourth** instance of the eval measuring something the product deliberately does not
do (after WP9.2, WP14, and the link-name/grain fix). It is deliberately NOT "fixed" here, because
the fix is a judgement call rather than a defect repair: crediting a deferral as coverage would
also hide a real regression in which the mapper stops resolving anything. Whoever picks this up
should decide explicitly whether an `unresolved` entry carrying *both* golden candidates counts as
covered, and pin that decision in a test either way.

Scale observation, honest rather than alarming: **27 of 59 concepts (46%) came back unresolved**,
against 0 at 30 tables. The deferral rate tracks cross-system overlap, not table count — the
100-table landscape is where the CRM/VEKTRA synonym pairs start dominating. The output is honest,
but "half the mapping needs ratification" is a real human-workload signal for the brownfield
track, and a reason the incremental-extension charter's domain-by-domain framing matters.

### Step: 300 tables (seed 42) — `scale_300`

_not run yet._ The transport ceiling no longer blocks it (see the modeler row above), and the
wall-clock blocker is fixed (Candidate #4). The open question at 300 is `emit_business_keys`,
which is already at 91% of cap at 100 tables, and the review queue, already at 1,121 items.

**Run the modeler probe before the full case — the order matters.** At 300 tables every agent
except one is already proven to degrade gracefully: `emit_requirements`, `emit_business_keys`
and `emit_mapping` all split on truncation (observed live), and `emit_contract_enrichment` sits
at 66% of cap and now runs concurrently (372 calls at 300 tables). `emit_dv_model` is the only
agent that *cannot* split — it emits one coherent model, and merging two half-models is a
modelling problem, not a plumbing one — so its budget is the only lever and the only genuine
unknown. If it overflows, the full `scale_300` cannot complete anyway, and paying ~$18 to
discover that mid-run repeats the serial-failure mistake recorded on 2026-07-28.

A targeted probe therefore runs only the modeler's real upstream dependencies —
`requirements_parser → business_key_identifier → dv2_modeler`, skipping `data_contract`, which
is sound because the modeler does not read contracts (verified against its state access) and
which is where most of the cost sits. Estimated ~$2–3 and ~10 minutes, against ~$18 and 30–45
minutes for the full case.

**Prediction to measure against** (from the two measured points, `tokens ~ tables^0.50`):
~23,080 output tokens = **70% of the 32,768 budget**, no truncation. That is the tightest
reserve in the pipeline at the one place without a fallback, and the exponent is a straight line
through exactly two points — it is an estimate, not a measurement. A green probe means
ADR-0010's deferred exit condition (staged modelling / domain partitioning) is not yet due at
300 tables; an overflow means it is a precondition rather than an option.

**Probe run 2026-07-29 — the modeler fits, but the probe did not test what it set out to test.**
228 s, one call per agent, no truncation anywhere:

| agent | calls | peak out | cap | %cap | truncations |
|---|---|---|---|---|---|
| `emit_requirements` | 1 | 7,061 | 8,192 | 86% | 0 |
| `emit_business_keys` | 1 | 4,606 | 8,192 | 56% | 0 |
| `emit_dv_model` | 1 | 13,833 | 32,768 | **42%** | 0 |

13,833 against a predicted ~23,080. That gap is the finding, not the good news — see
Candidate #5. The modeler was never handed a 300-table problem: it produced **38 hubs / 41 links
/ 55 satellites at 300 tables, against 68 / 21 / 35 at 100**. Its output plateaued because its
input did. **The modeler's scaling question is therefore still OPEN**, and the ~$18 full run
would currently measure the upstream collapse rather than the scale.

(An earlier attempt the same day was blocked by the account's API usage limit — `400
invalid_request_error`, nothing spent, the failure came on the first call. Worth one line
because it verified two things for free: the 400 was correctly *not* retried, `attempt=0` in the
trace per WP3's non-retryable matrix, and WP15 emitted the `llm_error` event for a propagating
non-retryable 4xx. The limit was gone ~10 minutes later; the message's stated reset date was not
reliable.)

## Breakpoints found → follow-up WPs

Each entry: symptom, size at which it appears, which agent/limit, proposed follow-up WP.

### Candidate #1 — `requirements_parser` output cap (`max_tokens=4096`)

- **Observed 2026-07-18** during tooling verification (an accidental single live call while
  checking the runner imports): on an *inventory-heavy* early draft of the 30-table
  requirements doc, `requirements_parser` raised `LLMCallError: response truncated at
  max_tokens=4096` — the parser tried to emit one requirement per named item and the tool
  payload exceeded its output budget. The run died at the very first agent.
- **Mitigation in the generator (this WP):** the requirements doc was made leaner — a
  business-entity/relationship *narrative* that scales with the entity count, not an
  exhaustive per-physical-table inventory — so the 30-step should now stay within the cap.
  Whether it still truncates, and at which N (100? 300?), is the **first thing to confirm
  live**; it is the most likely first hard breakpoint.
- **Likely follow-up WP:** raise/scale the `requirements_parser` output budget, or chunk its
  extraction the way the contract enricher was chunked (bounded per-section calls, folded
  back) — the same pattern that fixed the wide-schema contract truncation (CLAUDE.md
  2026-07-15). Confirm the exact breaking N first, then spec it.

### Candidate #2 — `mapping_accuracy` gate unmeasurable at scale (golden/scorer concept-name alignment)

> **Specced & landed as WP14** (`backlog-2026-07/wp14-scale-mapping-coverage-spec.md`,
> eval-only): the scale cases now score `mapping_match: column` — pair-based
> `mapping_coverage` + gateable `false_friend_hits`, with the concept-coupled scorers
> reported-only — and every result JSON carries the proposal dump. Concept mode
> (`bank`/`messy_insurance`) is unchanged. The live re-run below (§6 acceptance) is the
> maintainer's remaining step.

- **Observed 2026-07-19** on the first live `scale_30` run (3/3 repeats): `mapping_accuracy`
  = **0.069**, well below the 0.80 gate → `eval.run` exits 1. `pipeline_health`=1.0 and
  validation PASSED, so this is **not a crash or a pipeline regression** — the pipeline
  produced a healthy 17/7/~23 model and the gate simply cannot be met as currently wired.
- **Root cause — eval-side, structural, not a mapper-quality problem.** The scorer detail
  reads: `F1=0.07 (precision=1.00 1/1, recall=0.04 1/28); 50 proposals outside the golden
  universe, unscored`. Mechanism:
  - The mapper's concept work-list is the **free-form names the modeler assigns** — hub
    business keys and satellite attributes (`agents/source_mapper.py:148-151`).
  - `mapping_accuracy` matches a proposal to a golden concept by
    `normalize_identifier(concept)` string equality (`eval/scorers.py:265,272-274`;
    `normalize_identifier` = non-alnum→`_`, upper — a pure string fold).
  - The `scale_30` golden concepts are **business phrases** (`"partner name"`,
    `"branch of insurance"`, `"account number"`, `"iban"`). For **recall** to score, the
    LLM modeler must emit a hub-key/sat-attr string that normalises *identically* to each
    sampled phrase. At 30-table scale the generated concept vocabulary diverges almost
    entirely → recall 1/28, and ~50 of the model's ~51 concepts fall **out-of-universe**.
  - **precision is 1.00** — where a proposal *is* in the universe, the column pick is
    correct. So the mapper binds columns well; the scorer just can't align most of its
    concepts to the sampled golden phrases.
  - `gap_detection` = 0/3 is the same coupling (golden gaps are also keyed by concept name).
- **Why small cases don't show this:** `bank` / `messy_insurance` goldens were authored/
  tuned against the pipeline's *actual* concept output (WP9.1 re-measured live → 0.97). The
  synthetic `scale.generate` golden emits concepts in its **own** naming, with no mechanism
  binding the modeler's free naming to those strings. WP9.2 fixed the *precision* side
  (extra proposals don't count as wrong); the **recall** side still requires a name-matched
  proposal per golden concept, which free LLM naming at scale does not deliver.
- **Evidence strength:** structural, derived from the code + the scorer detail string. The
  50 out-of-universe proposals themselves were not persisted (`eval.run` uses `MemorySaver`,
  no disk dump); a one-run proposal dump would confirm concept-by-concept.
- **Proposed follow-up WP (decide with the architect — NOT yet implemented):**
  1. *Column-based recall* — score each golden entry by "does any proposal bind
     `golden.source_column` for `golden.entity`?" instead of by concept-string match. This
     measures the mapper's actual job (column binding) and decouples it from LLM naming. A
     deliberate scorer-semantics change, in the WP9.2 tradition.
  2. *Align the golden to real output* — dump one run's concepts and bind the sampled golden
     names to them; conflicts with the "byte-deterministic from `generate`" invariant.
  3. *Drop/loosen the scale gate* — the dataset.yml comment already frames scale as a
     *measurement* case; the current 0.80 gate is effectively unreachable and does not
     measure mapping quality.
  Recommendation on record: option 1 (column-based recall) — the other scores
  (`pipeline_health`, `validation_gate`, `driving_key_accuracy`) confirm the run itself is
  healthy, so the fix belongs in the scorer, not the pipeline.

- **Architect review (Cowork, 2026-07-19): diagnosis CONFIRMED against the code**
  (`scorers.mapping_accuracy` matches `normalize_identifier(p.concept)` against the golden
  universe; the mapper's work-list is the modeler's free-form `hub.business_key` +
  `sat.attributes`; `GoldenMappingEntry` already carries `source_table`/`source_column`, so
  column-based scoring needs no golden-format change). Option 1 is the right direction,
  **with three sharpenings** for the follow-up WP:
  1. Do NOT change `mapping_accuracy` semantics globally — the bank/messy goldens are
     name-aligned and measure the *stronger* concept-level correctness. Add a per-case
     scoring mode instead (dataset.yml `mapping_match: concept | column`, default
     `concept`), or equivalently a separate `mapping_coverage` scorer used by the scale
     cases. WP9.2 tradition: documented semantics change, pinned tests.
  2. Column mode scores **coverage, honestly named**: a golden mapping is recalled iff some
     proposal binds its `(source_table, source_column)` (normalised pair match only — do
     not couple to `entity`, entity naming diverges exactly like concept naming). The
     statistics trap survives (binding the GUID ≠ binding `PARTN_NR` → miss) and the
     false-friend check is already column-based. Do not construct a synthetic
     precision/F1 in column mode — gate on coverage ≥ 0.8 **plus zero false-friend hits**.
  3. `gap_detection` is concept-coupled on BOTH halves (gap recall *and* force-fit) and is
     therefore equally blind at scale — set it to reported-only for scale cases and say so
     in eval/README; the scale gap signal is the reported gap/unresolved counts plus human
     spot-check.
  Evidence step before implementing: persist the proposals into the result JSON (eval-only)
  and confirm the 50 out-of-universe concepts are modeler-naming variants, not mapper
  misbinds. Option 2 rejected (breaks generator determinism), option 3 alone rejected
  (loses the gate entirely). Candidate #1 assessment is also confirmed — chunking the
  parser like the contract enricher is the right pattern; confirm the breaking N first.
- **Specced as WP14** (2026-07-19): `backlog-2026-07/wp14-scale-mapping-coverage-spec.md`
  + kickoff — land before the `scale_100` live step.

### Candidate #3 — eval runner loses completed repeats on a mid-batch failure (operational)

> **Fixed (WP14.1).** `_run_score_write` now persists each repeat's JSON the moment
> it is scored; a mid-batch failure keeps every completed repeat on disk, prints a partial
> `n/m runs completed` summary, and exits non-zero. Success path unchanged.

- **Observed 2026-07-19** during the post-WP14 `scale_30` verification: the API credit
  balance ran out during run 2/3 (Anthropic 400, correctly non-retried by
  `ForcedToolCaller`); the process died with a traceback and run 1/3 — fully completed,
  scored, usage captured — was **not persisted**, because `_write_results` runs only after
  the whole repeat batch. Real money spent, no JSON.
- **Proposed follow-up (eval-only, S):** write each repeat's result JSON immediately after
  the repeat completes (crash-safe persistence); optionally catch per-repeat exceptions to
  flush partials and exit non-zero with the failure recorded. Fold into the next eval WP or
  do as a one-commit fix before the 100-step (where a mid-batch failure costs much more).
- **Protocol reminder:** the spec's budget rule is ONE repeat per step — use
  `--repeat 1` for gate/verification runs; the default is 3.

### Candidate #4 — `data_contract` wall clock: 129 independent calls run sequentially (FIXED)

- **Observed 2026-07-29**, first `scale_100` attempt. The run was killed at 50 minutes without
  ever reaching the two agents it existed to measure. Reading the trace rather than re-running
  showed why: `emit_contract_enrichment` had made **129 calls at ~21.7 s each = 46.8 of the
  run's 53.4 minutes — 88% of total wall clock**, while every other agent together took 6.
  129 was also exactly the predicted count (`sum(ceil(cols/40))` over 1,907 columns), so the
  agent had *finished*; the timeout landed on the threshold to `emit_dv_model`.
- **Not a token problem.** Peak output was 5,381 of 8,192 (66%) — WP19's adaptive split never
  fired, the pre-chunking bound held, and the cache hit rate was 96%. The units are independent
  by construction (one asset, one field chunk each). Nothing about the work required an order;
  only the code did.
- **Fixed the same day** in `agents/data_contract.py`: the first unit runs alone to write the
  shared prompt-cache entry (~14.7k tokens at 100 tables, which the other 128 read), then the
  remainder fan out under `_MAX_CONCURRENT_ENRICHMENTS = 8`. Bounded rather than unlimited on
  purpose — 129 simultaneous requests would trade a latency problem for a rate-limit one, and
  `ForcedToolCaller`'s backoff would then re-serialise them at a worse constant. Three
  properties are pinned by test because concurrency makes each easy to lose: results merge in
  **unit order**, not completion order (byte-identical artifacts); a failure raises the **first
  unit in order**, not the fastest to fail (same inputs, same error); and a failing warm-up
  stops before the fan-out instead of paying for 128 more calls to learn the same thing. The
  concurrency assertion was verified non-vacuous by forcing the bound to 1 and watching it fail.
- **Measured effect:** 46.8 min → 6.1 min for the same 129 calls; total run 53.4 min
  (incomplete) → 13.6 min (complete). Cache-read ratio *rose* to 405%.
- **Method note, the same lesson as 2026-07-28 and worth repeating:** the diagnosis cost nothing
  because the trace was already on disk. Read it before paying for another run.

### Candidate #5 — `requirements_parser` under-extracts SILENTLY at 300 tables (OPEN)

- **Observed 2026-07-29** by the 300-table modeler probe. The measurement, against the
  100-table run of the same day:

  | | doc chars | bullets | calls | requirements extracted | truncations |
  |---|---|---|---|---|---|
  | 100 tables | 9,027 | 93 | 4 | **113** | 2 → split, recovered |
  | 300 tables | 24,239 | 281 | 1 | **79** | 0 |

  A 2.7× larger document with 3× the bullets yielded **fewer** requirements, in one call, with
  no truncation. The parser summarised where it previously enumerated.
- **Why nothing caught it.** Every safety net in this pipeline keys on *truncation*:
  `stop_reason == "max_tokens"` triggers the adaptive split and the `INPUT_SEGMENTED` flag.
  Summarisation is not truncation. The response was well-formed, ended `tool_use`, and sat at
  86% of cap — indistinguishable, from the outside, from a document that genuinely contained 79
  requirements. There is no flag, no warning, and no scorer that fires. **This is the first
  failure mode found in this project that is silent by construction.**
- **Downstream consequence, measured:** 38 hubs / 41 links / 55 satellites at 300 tables against
  68 / 21 / 35 at 100. Fewer hubs from three times the landscape. Everything after the parser —
  business keys, the model, the mapping, the review queue — works from a compressed view of the
  source landscape and cannot know it.
- **It invalidates the probe's headline.** `emit_dv_model` used 42% of its budget not because it
  scales beautifully but because it was handed a 300-table *document* describing what amounts to
  a smaller problem. The ADR-0010 question — does one coherent model still fit at 300 tables —
  is **unanswered**, and the full `scale_300` should not be paid for until this is fixed, or it
  will measure the collapse instead of the scale.
- **Proposed follow-up (product, M).** Deliberately NOT specced here, because the obvious lever
  is one this project already rejected on evidence: a fixed character threshold is the wrong
  proxy, since output tracks content *density*, not length (the 2026-07-28 output-budget note —
  `messy_insurance` is larger than the 30-table document and yields far fewer requirements). The
  new datapoint is the mirror image and does not restore the threshold idea; it argues for a
  *coverage* signal instead. Candidate directions, in the order I would test them:
  1. a **structural completeness check** — compare extracted requirement count against countable
     structure in the document (bullets, headings) and flag a large shortfall for human review.
     Cheap, deterministic, and honest: it flags rather than guesses. Needs care not to fire on
     legitimately prose-heavy documents;
  2. **proactive segmentation above a structural size** (bullet/heading count, not characters),
     accepting the extra calls as the price of coverage;
  3. leaving it and documenting the ceiling — defensible only if the brownfield/domain-by-domain
     path (incremental-extension charter) is accepted as the sole supported route past ~100
     tables, which is in fact what that charter argues.
- **Method note:** the probe cost ~$1 and roughly 4 minutes and produced a finding the ~$18 full
  run would have buried in a plausible-looking result. Probing the one unknown before buying the
  whole measurement is the pattern to keep.

## Landscape composition (for interpreting the numbers)

The generator's controlled variables (`eval/scale/generate.py`): wide tables ~6%
(100–300 cols each, exercising modeler satellite splitting around
`SAT_WIDE_ATTRIBUTE_THRESHOLD`); relationship/junction tables ~22% (FK-comment traps →
WP9.1 demotion); ~30% of the primary entities multi-source (WP10 hubs); false-friend
columns ~12% of tables; a technical GUID shadowing the real key on ~50% of entity tables
(statistics trap); a sampled ~30-concept golden universe (WP9.2 semantics). All five
spike trap classes are present by construction and seeded/reproducible.
