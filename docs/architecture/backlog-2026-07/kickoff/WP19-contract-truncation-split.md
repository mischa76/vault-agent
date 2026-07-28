# Kick-off WP19 — data_contract truncation split (review finding 2026-07-28 #3)

You are a senior engineer putting the LAST list-shaped LLM agent onto the shared
truncation-split mechanism, so no enrichment density can kill a run. Keyless work — the
enricher is injectable.

## Read first
1. `CLAUDE.md` (canon; the 2026-07-28 "output-budget hardening" paragraph describes the
   two output shapes and why list-shaped output splits — you are applying that verdict).
2. `docs/architecture/backlog-2026-07/wp19-contract-truncation-split-spec.md` — the
   binding spec.
3. `src/vault_agent/llm.py` — `call_with_truncation_split` and `LLMCallError.truncated`
   (the contract you must not re-implement).
4. `src/vault_agent/agents/data_contract.py` in full (`_enrichment_units`,
   `_merge_enrichment`, `run`), and for the pattern to copy:
   `agents/business_key_identifier.py` (`split_requirements` — exact list halving) and
   `agents/source_mapper.py` (its INPUT_SEGMENTED flag wording).
5. `tests/test_agents/test_data_contract.py` — the batching pins you must keep green.

## What to build (spec §2, summarised — the spec wins on conflict)
1. Keep `_FIELDS_PER_CALL` pre-chunking (first-order bound, avoids doomed probe calls);
   wrap each unit's enrich call in `call_with_truncation_split` (unit = the chunk's field
   list, split = exact halving, `None` at a single field; merge = the existing
   `_merge_enrichment`).
2. One advisory `FlagKind.INPUT_SEGMENTED` flag per affected asset when a chunk split;
   NOT added to `REVIEW_FLAG_GROUPS`.
3. System prompt byte-identical across calls (WP3 caching); zero behaviour change when
   nothing truncates.
4. Correct the `_FIELDS_PER_CALL` comment: the 40×~200-token arithmetic claimed "well
   under" 8192 at ~98% — the review falsified it; the split is now the guarantee.

## Verify
- Spec §3 tests: truncated chunk → halves → full coverage + flag; non-truncation error
  propagates unsplit; indivisible truncation re-raises; both existing batching pins green
  with unchanged call counts.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green.

## Out of scope
`_MAX_TOKENS` / `_FIELDS_PER_CALL` value changes, streaming, scale re-measurement.

## Definition of Done
Spec §4 met; CLAUDE.md milestone paragraph appended; conventional commit(s) referencing
this kick-off and the spec.
