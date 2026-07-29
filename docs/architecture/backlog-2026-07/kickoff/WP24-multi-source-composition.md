# Kick-off WP24 — Multi-source hub composition (review findings 2026-07-29 #2/#3)

You are a senior engineer fixing the only defect class in this project that produces wrong
**data** rather than a wrong message: two feature combinations (WP7 satellite
`source_table`, WP8 roles, WP10 multi-source hubs) that each work alone and break together.
Both are reproduced in the review; neither is covered by a test or a gate. Keyless work.

## Read first
1. `CLAUDE.md` (canon; the WP7 §7.1, WP8/ADR-0009 and WP10 milestone paragraphs describe
   the three features you are composing).
2. `docs/architecture/reviews/project-review-2026-07-29.md` findings 2 + 3 (the probes and
   their output).
3. `docs/architecture/backlog-2026-07/wp24-multi-source-composition-spec.md` — binding spec.
4. `rules/dv2_rules.py` (`canonical_hub_key_column` — the helper written for exactly this,
   used in only two of its five call sites), `agents/staging_generator.py`
   (`collect_staging_specs`, all four `business_key` reads), `agents/code_generator.py`
   (the multi-source satellite branch and its existing GENERATION_GAP guard),
   `agents/validator.py` (gate patterns).
5. `tests/test_agents/test_multi_source_hub.py`, `tests/test_agents/test_staging_regression.py`,
   `tests/test_demo_bank_postgres.py` — the byte-identity you must not break.

## What to build (spec §2, summarised — the spec wins on conflict)
1. Route EVERY hub-key hash through `canonical_hub_key_column(hub)`: link participations,
   `source_table` satellites on a hub parent and on a link parent. Role qualification
   composes on top (`role_bk_column(canonical, role)`). Single-source output must stay
   byte-identical — pin the fixture BEFORE changing anything.
2. Reject the WP7+WP10 combination (`Satellite.source_table` on a hub with `sources`):
   validator gate `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB`, `GENERATION_GAP` flag from the generator,
   no per-source satellite models — and no orphaned `stg_<sat base>` model either (the
   staging generator must agree with the raw-vault generator about what is skipped).
3. `tests/test_agents/test_feature_composition.py`: the WP7 × WP8 × WP10 matrix, one
   assertion per cell, plus the invariant that no target column is ever hashed from two
   different input sets across a model's staging specs.

## Verify
- Spec §3 tests green; ungrounded staging baseline + bank demo guardrails untouched.
- The invariant test runs over every fixture model in the suite, not just the new ones.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.
- A real Postgres re-verification is NOT required (no template changed for the
  single-source path); if you touch a rendered template, it is.

## Out of scope
Giving the WP7+WP10 combination real semantics (needs an ADR), same-as links, and any
change to the `canonical_hub_key_column` policy itself.

## Definition of Done
Spec §4 met with evidence (name the probe outputs before/after); CLAUDE.md milestone
paragraph appended, stating plainly that the suite was blind to this because every existing
multi-source test used the disagreeing-feed case; conventional commit(s) referencing this
kick-off and the spec.
