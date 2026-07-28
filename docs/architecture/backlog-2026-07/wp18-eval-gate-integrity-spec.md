# WP18 — Eval gate integrity

Status: Proposed · Size: S · Depends on: — (eval/ only, no src/vault_agent change) ·
Source: project review 2026-07-28, finding 2

## 1. Problem — gates that pass on absence of evidence (fourth instance of the class)

After WP9.2 (out-of-universe proposals), WP14 (concept-naming blindness), and the
2026-07-28 vacuous-`_f1` fix, two holes of the same recorded class remain:

**(a) A gated scorer that never scored is silently skipped.** `failed_gates` checks
`name in stats` (`eval/run.py:215-221`). A typo'd scorer name in `min_scores`, or a
committed case whose `golden_mapping.yml` is missing (`materialize_case` returns `None` →
`_score_run` skips the mapping scorers), disables the gate without a word — exit 0.
scale_30 gates `mapping_coverage`: delete its golden mapping and the batch goes green.

**(b) The vacuity contract covers only the model scorers.** `load_eval_case` rejects
gating `construct_f1`/`driving_key_accuracy` on an empty golden (`eval/datasets.py:180-193`)
— but the mapping family is unprotected, and the *loader cannot protect it*: the golden
mapping lives in a separate file the loader never opens. `mapping_coverage` with zero
mappable golden entries returns a gateable 1.0 (`eval/scorers.py:407-411`). The
vacuous-details convention is also inconsistent: only `construct_f1`/
`driving_key_accuracy` emit the `"vacuous"` prefix that `vacuous_scorers()` and the
console marker key on; `confidence_calibration` even scores its nothing-to-check case 0.0
(`eval/scorers.py:480-481`) — the opposite polarity.

## 2. Target design [ENFORCE]

### 2.1 Missing gated scorer fails loudly (runner)

In `main` (per case, after `aggregate`): `missing = sorted(set(case.expectations.
min_scores) - set(stats))`. Non-empty → print
`GATE UNSATISFIABLE: <name> is gated but produced no score (typo'd scorer name, or the
case's golden mapping is missing)` to stderr, exit code 1. This is a *batch defect*, not a
score — it must never be conflated with a failed gate value.

### 2.2 One vacuity convention across every scorer

Contract (document in `eval/README.md`): **a scorer with nothing to check returns
score 1.0 and `details` starting with `"vacuous — "`.** Apply to:

- `mapping_coverage` (no mappable golden entries),
- `false_friend_hits` (no false friends declared),
- `gap_detection` (no golden gaps) — compose as `"vacuous — "` first, the
  `reported_only` note after, so the `startswith("vacuous")` key holds,
- `confidence_calibration` (no scored proposals): score 0.0 → **1.0** + prefix. Polarity
  fix; it was never gateable in column mode, but in concept mode it is, and 0.0 meaning
  "nothing to check" is the same defect as the pre-fix `construct_f1` 0.000, mirrored.
- `mapping_accuracy` ("no mappable concepts") gains the prefix (score already 1.0).

`construct_f1`/`driving_key_accuracy` already comply — do not touch them.

### 2.3 A vacuous score can never pass a gate (runner-side, generalising the loader rule)

The loader keeps its cheap early rejection for the model scorers. For everything the
loader cannot see, enforce at runtime: a gated scorer whose verdict was vacuous in
**every** repeat (reuse `vacuous_scorers()`) → `GATE UNSATISFIABLE: <name> is gated but
vacuous on this case (the golden declares nothing for it)`, stderr, exit 1. A gate must
fail loudly on absence of evidence, never pass on it.

### 2.4 Ablation parity

`eval.ablate` reuses `_score_run` but renders its own summary; it carries no `min_scores`
gate, so only §2.2 affects it (details text). Verify no ablation test pins the old
`confidence_calibration` polarity; update pins deliberately if one does.

## 3. Tests (keyless; extend `tests/test_eval_run.py` / `tests/test_eval_scorers.py` /
`tests/test_mapping_scorers.py`)

1. Gated-but-missing scorer → exit 1 + `GATE UNSATISFIABLE` (typo case and
   missing-golden-mapping case).
2. Gated-but-all-vacuous scorer → exit 1 + the vacuity message; the same scorer
   non-vacuous and above threshold → exit 0 (no false positive).
3. Each §2.2 scorer: vacuous verdict is 1.0 + prefix; `vacuous_scorers()` picks all of
   them up; `render_table` marks them.
4. `gap_detection` column mode: prefix composition order pinned.
5. Polarity regression: `confidence_calibration` with real correct/wrong proposals
   unchanged (existing pins stay green untouched).

## 4. Acceptance criteria

1. Deleting `eval/datasets/scale_30/golden_mapping.yml` in a scratch copy makes the
   runner exit 1 with `GATE UNSATISFIABLE` (manual check, not a committed test).
2. `grep -rn '"vacuous' eval/scorers.py` shows one convention (prefix + 1.0) for every
   nothing-to-check branch.
3. Existing scorer pins pass untouched except the two deliberately changed
   (`confidence_calibration` vacuous polarity, `gap_detection`/`mapping_accuracy`/
   `mapping_coverage`/`false_friend_hits` details prefixes) — name them in the commit.
4. Standard DoD; no `src/vault_agent/` change.

## 5. Out of scope

Name-keyed hub/satellite matching (recorded README caveat), new scorers, and any gate
threshold change. scale_100 measurement work stays its own track.
