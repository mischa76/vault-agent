# Scale-hardness test findings (WP13 / Charter A)

Status: **template — live half not yet run** · Owner: Mischa Eismann · Spec:
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

| Measure | Value |
|---|---|
| Date / git SHA | _tbd_ |
| Models (primary / heavy) | _tbd_ |
| Wall-clock | _tbd_ |
| LLM calls | _tbd_ |
| Input tokens (cache-read share) | _tbd_ |
| Output tokens | _tbd_ |
| Cost estimate | _tbd_ |
| Hubs / links / satellites | _tbd_ |
| Validation verdict (+ issue counts) | _tbd_ |
| mapping_accuracy (vs sampled golden) | _tbd_ (gate ≥ 0.80) |
| gaps / unresolved | _tbd_ |
| Review items / rendered lines | _tbd_ |
| report.html size · Mermaid graph renders? | _tbd_ |
| First hard failure (agent / limit) | _none / tbd_ |

Notes: _tbd_

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

## Landscape composition (for interpreting the numbers)

The generator's controlled variables (`eval/scale/generate.py`): wide tables ~6%
(100–300 cols each, exercising modeler satellite splitting around
`SAT_WIDE_ATTRIBUTE_THRESHOLD`); relationship/junction tables ~22% (FK-comment traps →
WP9.1 demotion); ~30% of the primary entities multi-source (WP10 hubs); false-friend
columns ~12% of tables; a technical GUID shadowing the real key on ~50% of entity tables
(statistics trap); a sampled ~30-concept golden universe (WP9.2 semantics). All five
spike trap classes are present by construction and seeded/reproducible.
