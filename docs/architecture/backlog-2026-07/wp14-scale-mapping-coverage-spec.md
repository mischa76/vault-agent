# WP14 — Scale mapping scoring: column-based coverage mode (eval-only)

Status: Proposed · Size: S · Depends on: WP13 (landed). Must land **before** the
`scale_100` live step — the current gate measures naming alignment, not mapping quality.
Origin: `../scale-test-findings.md` Candidate #2 (diagnosis + architect review
2026-07-19, confirmed against the code).

## 1. Problem

`mapping_accuracy` matches proposals to golden entries by
`normalize_identifier(concept)` equality. On the synthetic scale cases the mapper's
concepts are the **modeler's free-form names** while the golden concepts are the
**generator's own vocabulary** — at 30 tables they diverge almost entirely (measured
2026-07-19: recall 1/28, precision 1.00, ~50 of ~51 proposals out-of-universe, gate
failed 3/3 with a perfectly healthy pipeline). The name-aligned goldens of
`bank`/`messy_insurance` don't have this problem and must keep their stronger,
concept-level semantics unchanged.

## 2. Design (all in `eval/`, no `src/vault_agent` change)

### 2.1 Per-case scoring mode

`EvalCase` gains `mapping_match: Literal["concept", "column"] = "concept"`
(dataset.yml field, loader-validated). `concept` = today's behaviour, byte-identical —
the existing pinned scorer tests must pass untouched.

### 2.2 `mapping_coverage` scorer (column mode)

For each golden mapping entry: **recalled iff any proposal's normalised
`(table, column)` pair equals the entry's `(source_table, source_column)`**; an
`ambiguous` entry is recalled by any listed candidate pair. Score = recalled / mappable.
Deliberately:

- Pair match only — **no `entity` coupling** (entity naming diverges exactly like
  concept naming; a wrong-table bind can never score because the pair differs).
- The statistics trap survives: binding the shadow GUID is a different pair → miss.
- **No synthetic precision/F1 in column mode** — coverage is what the mode can honestly
  measure; naming it `mapping_coverage` (not `mapping_accuracy`) keeps the semantics
  visible in every result JSON and gate.
- Details string reports recalled/missed counts, missed pairs (first few), and the
  out-of-universe-analog: proposals binding columns outside the golden column set are
  counted and reported, never penalised (WP9.2 tradition).

### 2.3 `false_friend_hits` scorer (column mode)

The false-friend check is already column-based; in column mode it becomes its own
gateable score: **1.0 when no proposal binds a golden `false_friends` pair, else 0.0**,
hits listed in the details. This preserves the "coverage ≥ 0.8 AND zero false-friend
hits" gate the findings review requires (min_scores entries are per-scorer, so the
compound gate is two lines).

### 2.4 `gap_detection` at scale: reported-only

Gap recall AND the force-fit check are both concept-name-coupled, so in column mode the
scorer is blind on both halves. In column mode `gap_detection` is still computed and
reported, with a details prefix marking it non-gateable ("concept-coupled — reported
only in column mode"); the **loader rejects** a column-mode case whose `min_scores`
names `gap_detection` or `mapping_accuracy` (attributable error naming field + case,
house loader style). The scale gap signal is the reported gap/unresolved counts plus
human spot-check — documented in `eval/README.md`.

### 2.5 Proposal dump (evidence, all cases)

`eval/run.py` writes `state.mappings.model_dump()` (proposals + gaps + unresolved) into
each result JSON (new `mappings` key). Cheap, keyless-testable, and closes the findings'
open evidence step: one `scale_30` re-run then shows concept-by-concept whether the
out-of-universe proposals are naming variants (expected) or misbinds.

### 2.6 Case updates

`scale_30/dataset.yml`: `mapping_match: column`; `min_scores: {mapping_coverage: 0.8,
false_friend_hits: 1.0, pipeline_health: 1.0}`. `scale_100`/`scale_300`: `mapping_match:
column`, still ungated. `bank`/`messy_insurance`: untouched (default `concept`).

## 3. Tests (keyless, in the existing eval test modules)

Pinned `mapping_coverage`: full/partial/zero coverage · GUID-trap pair miss · ambiguous
candidate hit · entity divergence irrelevant (same pair, different entity → hit) ·
out-of-golden-column proposals reported, unscored. `false_friend_hits`: clean → 1.0,
one hit → 0.0 + detail. Loader: `mapping_match` default + rejection of
`gap_detection`/`mapping_accuracy` gates in column mode (attributable message). Runner:
result JSON carries `mappings`; concept-mode scorer outputs byte-identical for the
existing fixtures (regression pin).

## 4. Acceptance criteria

1. Existing scorer/eval tests pass unchanged (concept mode untouched).
2. `scale_30` gates on `mapping_coverage` + `false_friend_hits` + `pipeline_health`;
   loader-rejects a concept-coupled gate in column mode.
3. Result JSONs carry the proposal dump (stub-verified).
4. `eval/README.md` documents both modes and why gap_detection is reported-only at
   scale; `scale-test-findings.md` Candidate #2 gets a one-line "specced/landed as WP14"
   pointer.
5. Full suite + ruff + mypy (incl. eval/) green; no `src/vault_agent` change, no new
   dependency.
6. (Live, after merge) one `scale_30` re-run: gate verdict now reflects mapping quality;
   the proposal dump confirms the naming-variant hypothesis — recorded in the findings.
