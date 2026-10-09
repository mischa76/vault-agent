---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP59 — The model switch as a pre-registered experiment: Sonnet 5.5 / Opus 5.5 against the 4.x record

Status: **Approved and in progress** (2026-10-09, user: „du hast mein go für 1.: das experiment mit
modellwechsel mit Neumessung im vergleich“) · Owner: Mischa Eismann · Author: Claude. No code
change: the models are configuration (`PRIMARY_MODEL`, `HEAVY_MODEL`), the measurement is the
chain and the steering ledger's release protocol. Nothing is switched by default until §6 says
what the switch does.

## 1 Starting point, measured

vault-agent runs `claude-sonnet-4-6` (primary) and `claude-opus-4-8` (the modeler) — one model
generation behind the API's offer (`docs/log.md` 2026-10-09: Opus 5.5 since 2026-09-21, Sonnet 5.5
since 2026-09-28). Prices from the pricing page (platform.claude.com, read 2026-10-09), per
million tokens — input / 5-minute cache write / cache read / output:

| model | input | cache write | cache read | output |
|---|---|---|---|---|
| Opus 4.8 (now) | 5 | 6.25 | 0.50 | 25 |
| **Opus 5.5** | **4** | 5 | 0.20 | **20** |
| Sonnet 4.6 (now) | 3 | 3.75 | 0.30 | 15 |
| **Sonnet 5.5** | **2** | 2.50 | 0.10 | **10** |

The eleven recorded 4.x chains give the comparison its distribution: decisions mean 138.8, sd
8.6 (ceiling 155.1 for the next 4.x chain); attempts per step 1–3; all-green in 7 of 11; cost
6.4–7.7 USD; WP34 §6 held in full on 5 of the last 6. The steering ledger demands, on any model
bump, the release protocol: gated cases × rules with a backstop, 3 repeats per arm, verdict per
row.

## 2 The experiment

1. **One chain on 5.5**: `PRIMARY_MODEL=claude-sonnet-5-5 HEAVY_MODEL=claude-opus-5-5`, one
   repeat of `adventureworks_incremental`, everything else as the eleventh chain (`09e3c01`+).
   Judged by the same checker against the 4.x distribution; **not** entered into
   `REVIEW_DECISION_SAMPLES` (a different model is a different population — the record stays 4.x
   until a switch is decided).
2. **The ledger's cheap matrix on the candidate modeler**: the two rules with a backstop —
   `cdk_not_payload` (`attributes_without_cdk`) on `health_insurance`, `effsat_two_dates`
   (`effsat_two_attributes`) on `bank` — via `eval.ablate --model claude-opus-5-5 --repeat 3`,
   baseline arm against dropped arm; verdict per row by the protocol (any backstop fire in the
   dropped arm → keep). Budget ≈ 12 single-case runs.
3. **Read before believing**: the 5.5 chain's trace, construct by construct where the numbers
   surprise (ledger: „a score delta without a mechanism is a hunch“).

## 3 Pre-registration (the chain)

**P1** — all five steps green. **P2** — attempts per step ≤ the 4.x pattern (no step needs three).
**P3** — WP34 §6 holds in full; decisions within the 4.x ceiling 155.1; links ≥ 8; invention ≤ 2;
joins 0/0. **P4** — backstop fires: `attributes_without_cdk` ≤ the 4.x range (4–10 per chain);
`one_hub_link_collapsed`, `retired_reemitted`, `satellite_relation_inferred` reported, not predicted.
**P5** — cost ≤ 6 USD at the 5.5 prices (the 4.x chains: 6.4–7.7) with the same token volume ± 20 %;
wall clock reported. **P6** — WP57 carry-over ≥ 90 % on every retry, as on the eleventh chain.
**Not predicted** — which shapes the modeler builds; whether 5.5 makes *fewer* gates fire (the
interesting outcome) or merely different ones.

## 4 Pre-registration (the matrix)

Both rules: the dropped arm on Opus 5.5 shows **at least one backstop fire** in 3 repeats →
`keep`, as on every model so far. A clean dropped arm with no gated-score regression is a
`candidate-delete` for a human to decide, with the origin column read first.

## 5 Decision rule

A switch of the defaults is proposed only if P1–P3 hold and the cost is lower; it is then its
own entry (config change, cost records, ledger rows updated to the new model) and the review
record restarts for the new population. One chain is a shape, not a distribution — a second 5.5
chain before any default change.

## 6 Results

*(appended after the runs)*

**2026-10-09 — the chain (§2.1), after two false starts the client could not make (WP60).**
`20261009T161212987101Z`: all five steps green, 22.6 min, 4.91 USD at the 5.5 prices (6.89 at 4.x for the same
tokens), invention 0, links 21, joins 0/0, **review 238 against 155.1 — failed on one defect**:
Sonnet 5.5 stringified the contract tool's `assets` in 10 of 68 answers (one brace too many), the
old backstop dropped them, 158 fields lost their types. WP61 widens the backstop. Zero backstop
fires on the whole chain; WP57 carry-over 100 % on retries; WP60's auto mode 0 of 114 without a
tool block. P1, P5, P6 held; P2 failed (step 1 took three attempts); P3 failed on review only; P4
reported. §2.2 (the matrix) is running. §5's decision rule: a second 5.5 chain with WP61 before
any default change.
