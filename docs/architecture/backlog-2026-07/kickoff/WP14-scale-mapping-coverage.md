# Kick-off WP14 — Column-based mapping coverage for scale cases (eval-only)

You are a senior Python engineer working on **vault-agent** (this repository). Your task
is exactly one small, eval-only work package: the scale cases get an honest,
column-based mapping score. One commit is fine. **No file under `src/vault_agent/` may
change.**

## Read first, in this order
1. `docs/architecture/scale-test-findings.md` — Candidate #2 (the measured failure, the
   confirmed root cause, and the architect-review sharpenings you are implementing).
2. `docs/architecture/backlog-2026-07/wp14-scale-mapping-coverage-spec.md` — your spec.
3. `eval/scorers.py` — `mapping_accuracy`, `gap_detection`, `_acceptable_pairs`,
   `_golden_universe`, `_false_friend_pairs`, `score_mapping` (the WP9.2 semantics you
   must NOT change in concept mode); `eval/mapping.py` — `GoldenMappingEntry`
   (`source_table`/`source_column` — the pair you match on), `AmbiguousEntry`.
4. `eval/datasets.py` — `EvalCase`/`Expectations` + loader validation style
   (attributable errors); `eval/run.py` — `score_mapping` call site, result-JSON
   assembly, `min_scores` gating.
5. `eval/datasets/scale_30/dataset.yml` (the case you re-gate) and the existing pinned
   tests in `tests/test_mapping_scorers.py` / the eval test modules (your regression
   baseline — they must pass untouched).
6. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.

## Task
Spec §2: `EvalCase.mapping_match` (default `concept`, byte-identical behaviour) ·
`mapping_coverage` scorer (normalised pair match, no entity coupling, no synthetic F1,
out-of-golden-column proposals reported not penalised) · `false_friend_hits` scorer
(1.0/0.0, gateable) · `gap_detection` reported-only in column mode + loader rejection of
concept-coupled gates · proposal dump (`state.mappings.model_dump()`) into every result
JSON · re-gate `scale_30`, set `mapping_match: column` on all three scale cases ·
`eval/README.md` mode documentation + findings pointer.

## Constraints
- Concept mode stays byte-identical — existing scorer tests are the regression pin; do
  not edit them except to add new cases.
- The trap semantics must survive in column mode (GUID pair miss; false-friend hits
  detected) — pin both with tests.
- Loader errors are attributable (name the dataset file, the field, and why), matching
  the `source_schema.load_source_schemas` style.

## Definition of Done
Spec acceptance criteria 1–5 verified (6 is the maintainer's live re-run — your handover
names the exact command and what to look for in the proposal dump) · all new tests
keyless · `uv run pytest -q` / `ruff` / mypy (incl. eval/ per the mypy config) green ·
CLAUDE.md milestone paragraph · conventional commit referencing the spec.
