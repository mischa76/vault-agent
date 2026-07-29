# Kick-off WP22 — Streaming in ForcedToolCaller (ADR-0010, Accepted 2026-07-29)

You are a senior Python engineer moving the single shared LLM call path from
non-streaming to streaming, lifting the transport ceiling that blocks scale_100/300.
Keyless work — the live smoke test is the maintainer's, not a merge gate.

## Read first
1. `CLAUDE.md` (canon; the 2026-07-28 output-budget paragraph explains why 16384 was a
   stopgap and why the modeler cannot split).
2. `docs/architecture/adrs/ADR-0010-modeler-output-scaling.md` — the decision this
   implements, incl. what is deliberately NOT built (staged modelling).
3. `docs/architecture/backlog-2026-07/wp22-streaming-spec.md` — the binding spec.
4. `src/vault_agent/llm.py` in full (call loop, retry matrix, truncation, usage/trace
   seams) and `agents/dv2_modeler.py` (`_MAX_TOKENS` + its measured comment block).
5. The INSTALLED anthropic SDK source for `messages.stream` / `get_final_message`:
   final-message shape, exception surface mid-stream, timeout semantics under streaming.
   **Verify, never assume — the WP8 t_link lesson.** Also verify the configured
   `heavy_model`'s max output tokens against the live docs before picking the new budget.
6. `tests/test_llm.py` in full — every behaviour there is re-pinned, not re-invented.

## What to build (spec §2, summarised — the spec wins on conflict)
1. `ForcedToolCaller.call`: `messages.create` → `messages.stream(...)` +
   `get_final_message()`; ONE code path, request kwargs byte-identical (cache-controlled
   system block, tools, tool_choice), retry/backoff/truncation/missing-block/usage/trace
   semantics unchanged.
2. Stub-client seam: stream context manager + `get_final_message()`; update every stub
   that feeds `ForcedToolCaller`.
3. `dv2_modeler._MAX_TOKENS`: raise to a deliberate budget under the verified model
   limit, covering the ~26k @ 300-tables extrapolation with headroom; replace the
   stopgap comment with an ADR-0010 pointer.

## Verify
- Spec §3 matrix green: payload/kwargs pin, truncation raise + events, retry paths,
  raising-recorder guards, modeler budget pin.
- `rg "messages.create" src/vault_agent` → nothing.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy` green; prompt/steering
  fixtures untouched.

## Out of scope
Staged modelling, budgets of the splitting agents, progress reporting, any beta
streaming feature.

## Definition of Done
Spec §4 met with evidence; CLAUDE.md milestone paragraph appended (state explicitly that
the live streaming smoke is still open if you could not run it); conventional commit(s)
referencing this kick-off, the spec, and ADR-0010.
