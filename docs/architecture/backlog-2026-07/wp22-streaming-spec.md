# WP22 — Streaming in ForcedToolCaller

Status: Proposed · Size: S/M · Depends on: ADR-0010 (Accepted 2026-07-29) ·
Source: ADR-0010 decision (Option A)

## 1. Problem

The shared `ForcedToolCaller` is non-streaming, which caps every LLM call's output at
the transport level: non-streaming requests risk HTTP timeouts above roughly 16k output
tokens (the SDK itself refuses/warns on non-streaming requests whose expected duration
is too long). The modeler — the one agent whose output cannot be split — sits at 91% of
its 16384 stopgap at 100 tables; the 300-table extrapolation (~26k tokens) does not fit.
ADR-0010 decided: lift the transport ceiling by streaming, centrally, before any
modelling-architecture change.

## 2. Target design [ENFORCE]

### 2.1 One call path, now streaming

`ForcedToolCaller.call` switches from `client.messages.create(...)` to the SDK's
streaming helper (`client.messages.stream(...)` context manager +
`get_final_message()`), keeping EVERYTHING else identical: forced single tool +
`tool_choice`, the cache-controlled system block (WP3 — request kwargs byte-identical),
retry/backoff on the same exception classes (an error raised mid-stream surfaces from
the helper the same way; **verify the exception surface against the installed SDK** —
the WP8 t_link lesson), truncation detection on the final message's
`stop_reason == "max_tokens"`, `_tool_payload` on the final message's content blocks,
usage capture and WP15 trace events from the final message. One code path — no
streaming/non-streaming conditional: a second path is a second thing that can rot.

Notes for the implementer, to verify live rather than assume: (a) the stream helper
accumulates tool-input JSON deltas and yields a final message shape-identical to the
non-streaming response (content blocks, `stop_reason`, `usage`, incl.
`cache_read_input_tokens`); (b) client-level timeout semantics under streaming (the
per-chunk read timeout replaces the whole-request timeout); (c) whether
`anthropic.APIStatusError` mid-stream carries `status_code` as before (retry loop keys
on it).

### 2.2 Test seam

The injectable stub client (`tests/test_llm.py` and every agent stub that goes through
`ForcedToolCaller`) grows a `messages.stream(...)` context manager returning an object
with `get_final_message()`; the recorded request kwargs assertions (system block with
`cache_control`, tools array, `tool_choice`, `max_tokens`) carry over unchanged. All
existing `test_llm.py` semantics (truncation raise, missing tool block, retry/backoff
paths, usage/trace recorders incl. the raising-recorder guards) are re-pinned against
the streaming path — same behaviours, new transport.

### 2.3 Raise the modeler budget deliberately

With the transport ceiling gone, `dv2_modeler._MAX_TOKENS` moves from 16384 to a
deliberate budget: **verify the configured `heavy_model`'s max output tokens against the
live docs**, then set the budget to cover the 300-table extrapolation (~26k) with
headroom, bounded by the model limit. Replace the stopgap comment block with the new
rationale and a pointer to ADR-0010 (which records the exit condition toward staged
modelling / domain partitioning). Other agents' budgets stay unchanged — they split, and
their budgets were measured, not transport-capped.

### 2.4 What must not change

- Request content byte-identical (prompts, tools, system block) — prompt caching and the
  WP16 fixture pins are untouched.
- `LLMCallError` semantics identical: `truncated` attribute, message wording, the
  callers' `call_with_truncation_split` behaviour.
- Trace/usage numbers keep their meaning (final-message usage, one `llm_call` event per
  completed response, `llm_error` on terminal failures).

## 3. Tests (keyless)

1. Streaming stub: payload returned, request kwargs pinned (cache-controlled system
   block present), tool payload extracted from the final message.
2. Truncation: final message with `stop_reason="max_tokens"` → `LLMCallError(truncated=
   True)`, usage recorded, `llm_call` + `llm_error` events emitted (unchanged semantics).
3. Missing tool block → `LLMCallError`; retryable status mid-stream → backoff retry;
   non-retryable 4xx → traced and propagated. (Re-pin the existing matrix.)
4. Usage/trace recorder guards (incl. raising recorders) green on the streaming path.
5. Modeler budget: pinned to the new constant; the comment references ADR-0010.

## 4. Acceptance criteria

1. `rg "messages.create" src/vault_agent` finds nothing (single streaming path).
2. All existing `test_llm.py` behaviours re-pinned and green; no agent code changed
   except the modeler's `_MAX_TOKENS` + comment.
3. Live smoke (maintainer, when API budget exists — not a merge gate): one real modeler
   call streams and lands in the trace with usage numbers; noting it in CLAUDE.md
   closes the WP.
4. Standard DoD.

## 5. Out of scope

Staged modelling, domain partitioning (charter track), budget changes to the splitting
agents, fine-grained tool-streaming betas, progress UI.
