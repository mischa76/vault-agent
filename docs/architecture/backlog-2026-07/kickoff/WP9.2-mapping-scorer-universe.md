# Kick-off WP9.2 — Mapping scorers: score only the golden concept universe

You are a senior Python engineer fixing ONE eval-design artefact found in the bank live
run (2026-07-13). Self-contained kick-off, eval-only, size S. Keyless except the optional
final re-measurement.

## The finding (evidence)

Bank live eval after WP9.1: `mapping_accuracy F1=0.80 (precision=0.67 6/9, recall=1.00
6/6)`, `confidence_calibration margin=0.01 (correct=0.97 n=6, wrong=0.96 n=3)` —
identical across 3 runs. Recall 6/6 shows the mapper is CORRECT (both hub keys resolve,
WP9.1 works). The precision hit comes from 3 proposals for concepts of the *generated*
model that the golden mapping does not cover (the bank modeler routinely adds
transactions/addresses; their attributes get mapped — correctly — but count as "wrong").
The spike never saw this because its prototypes were fed the GOLDEN model's concepts;
the live pipeline maps the GENERATED model's concepts. The same artefact collapses the
calibration margin (the "wrong" n=3 are confident because they are actually fine).

## The fix (eval/scorers.py + tests only — no src/ changes)

1. Define the **golden concept universe** per case: every concept in
   `golden_mapping.yml`'s `mappings` + `gaps` + `ambiguous` (normalised via
   `rules.normalize_identifier`).
2. `mapping_accuracy`: score ONLY proposals/gaps/unresolved whose concept is in the
   universe. Precision denominator = scored proposals; recall unchanged (golden side).
   Out-of-universe proposals are NOT penalised — count them in `details` as
   `"N proposals outside the golden universe, unscored"`.
3. `confidence_calibration`: same restriction — correct/wrong sets drawn from scored
   proposals only.
4. `gap_detection`: verify it is already universe-safe (it scores golden gaps; the
   force-fit penalty must keep considering ALL proposals that map a golden-gap concept —
   that check stays global by design).
5. Keyless tests: pin the bank artefact as a fixture (6 golden concepts, 9 proposals of
   which 3 out-of-universe, all confident) → expect F1=1.00, calibration computed over
   n=6/n=0 (define the no-wrong-proposals margin explicitly — recommend 1.0 with a
   details note, not 0.0), details mention "3 … unscored". Keep/adjust the existing
   pinned-score tests (scores for in-universe fixtures must not change).
6. AFTER the fix: set `min_scores.mapping_accuracy` for the bank case (recommend 0.95)
   in `eval/datasets/bank/dataset.yml` — the gate the WP9 spec §8 deferred until a
   clean baseline existed.
7. Optional (needs API key): one `--dataset bank` re-run; expected
   `mapping_accuracy=1.00`, calibration meaningful. Paste into the report and CLAUDE.md.

## Constraints

Do not change the mapper, the golden files, or `ProposedMapping` — the scorer adapts to
the pipeline reality, not the other way round. Do not silently redefine scorer semantics
beyond the universe restriction; document the change in `eval/README.md` (scorer
semantics section) and in a short CLAUDE.md milestone line dated accordingly.

## Definition of Done

pytest/ruff/mypy green (incl. eval/) · pinned tests for the universe restriction + the
no-wrong-margin definition · eval/README + CLAUDE.md updated · conventional commit
referencing this kick-off · report with the (optional) re-measured bank table.
