# WP19 — data_contract on the truncation split

Status: Proposed · Size: S · Depends on: — · Source: project review 2026-07-28, finding 3

## 1. Problem

`data_contract` is the last list-shaped agent without the truncation split. The enricher
chunks by a fixed `_FIELDS_PER_CALL = 40`, and its own margin arithmetic is thin: the
comment claims ~200 output tokens/field worst case, which is ~8,000 of the 8,192 budget
(`data_contract.py:46-51`). A denser-than-assumed chunk truncates →
`ForcedToolCaller` raises `LLMCallError(truncated=True)` → **the whole run dies** at the
third pipeline stage (and until WP17 lands, dies unrecoverably). The 2026-07-28
output-budget milestone's own argument applies verbatim: a fixed threshold is the wrong
proxy — output tracks content density, not field count.

The requirements parser, business-key identifier, and source mapper all share
`llm.call_with_truncation_split`; the mechanism and its bounded recursion
(`MAX_SPLIT_DEPTH`) are proven. This WP closes the gap.

## 2. Target design [ENFORCE]

### 2.1 Keep the pre-chunking, add the adaptive safety net

Two layers, deliberately both:

- **Pre-chunking stays.** `_FIELDS_PER_CALL = 40` avoids paying a doomed full-budget
  probe call on tables known to be wide (the adaptive shape's stated cost: the triggering
  call burns its output budget for nothing). It is the cheap first-order bound.
- **Truncation split per chunk.** Wrap the per-unit call in
  `call_with_truncation_split`: unit = the field-label list of one chunk, `split` = exact
  halving (the `split_requirements` pattern — a list, no boundary search; `None` when a
  single field is left), `call` = `enricher.enrich` with `{name: chunk}` as before. Merge
  = the existing `_merge_enrichment` folds each returned slice; field order is preserved
  by construction (halves keep order).

An indivisible single-field chunk that still truncates re-raises — that is not a size
problem and must surface (the shared helper's contract).

### 2.2 Flag the segmentation

When any chunk of an asset had to split, raise one advisory
`FlagKind.INPUT_SEGMENTED` flag per affected asset (`asset` = the asset name, message
naming the segment count) — same convention as the parser/identifier/mapper. Do NOT add
the kind to `REVIEW_FLAG_GROUPS`: it fires once per asset, like the parser's per-document
flag, and must stay individually visible.

### 2.3 What must not change

- System prompt stays byte-identical across all calls (the WP3 caching property) — the
  split changes only `user_content`.
- Normal-width runs make exactly the same calls as today (one per unit, unchanged
  content) — the segmentation is invisible until needed. Pin this.
- The deterministic contract core (`_build_contract`, tests emission, flags) untouched.

## 3. Tests (keyless, stub enricher; extend `tests/test_agents/test_data_contract.py`)

1. Enricher raising `LLMCallError(truncated=True)` for a 40-field chunk, succeeding on
   its 20-field halves → all fields enriched, one INPUT_SEGMENTED flag with the asset
   name, `_merge_enrichment` coverage intact.
2. Non-truncation `LLMCallError` propagates unsplit (the shared helper's contract,
   pinned here too).
3. Indivisible single-field truncation re-raises.
4. Regression: the existing batching pins (`test_enrichment_is_batched_one_asset_per_call`,
   `test_wide_table_is_chunked_and_fully_enriched`) pass with unchanged call counts and
   payloads when nothing truncates.

## 4. Acceptance criteria

1. No fixed-width assumption can kill a run: any enrichment density completes or fails
   attributably (indivisible-and-still-truncated), never as an unhandled mid-pipeline
   crash.
2. Byte-identical behaviour (calls, payloads, contracts) when no truncation occurs.
3. Update the `_FIELDS_PER_CALL` comment: it is now the *first-order bound*, the split is
   the guarantee — remove the "keeps a full chunk well under" claim the review falsified.
4. Standard DoD.

## 5. Out of scope

Raising `_MAX_TOKENS`, changing `_FIELDS_PER_CALL`, streaming, and the peak-utilisation
re-measurement table (that belongs to the scale track).
