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

_not run yet_

### Step: 300 tables (seed 42) — `scale_300`

_not run yet_

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

## Landscape composition (for interpreting the numbers)

The generator's controlled variables (`eval/scale/generate.py`): wide tables ~6%
(100–300 cols each, exercising modeler satellite splitting around
`SAT_WIDE_ATTRIBUTE_THRESHOLD`); relationship/junction tables ~22% (FK-comment traps →
WP9.1 demotion); ~30% of the primary entities multi-source (WP10 hubs); false-friend
columns ~12% of tables; a technical GUID shadowing the real key on ~50% of entity tables
(statistics trap); a sampled ~30-concept golden universe (WP9.2 semantics). All five
spike trap classes are present by construction and seeded/reproducible.
