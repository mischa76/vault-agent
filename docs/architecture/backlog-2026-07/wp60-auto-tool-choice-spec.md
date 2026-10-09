---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP60 — A tool-call mode for models that refuse forced tool use

Status: **Approved and in progress** (2026-10-09, a prerequisite of WP59, the model-switch
experiment the user approved: „das experiment mit modellwechsel mit Neumessung im vergleich“) ·
Owner: Mischa Eismann · Author: Claude. Touches `llm.ForcedToolCaller` and one setting. No prompt
change in the default mode; the default mode's request is byte-identical.

## 1 Problem, measured

The twelfth chain's first call (`docs/log.md` 2026-10-09) failed before any token was billed:
`400 invalid_request_error: tool_choice: type "tool" and "any" are not supported for this model`.
Verified in the tool-use documentation (platform.claude.com, „Forcing tool use“, read
2026-10-09): **Claude Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1 return a 400 for `any` and
`tool`**; what to use instead is `auto` with strict tool use to guarantee schema-valid inputs
(„prompting still influences which tool `auto` picks“), or structured outputs. Every agent of
this pipeline calls one tool, forced, through `ForcedToolCaller` (WP3) — so the whole pipeline is
closed to the current model generation until the client can ask instead of force.

## 2 The rule

**Setting `forced_tool_choice` (env `FORCED_TOOL_CHOICE`, default `true`) selects the mode; the
default request does not change by a byte.**

1. Forced (default): `tool_choice: {"type": "tool", "name": <tool>}`, as today — pinned by
   `test_request_kwargs_are_unchanged_by_the_transport_switch`.
2. Auto: `tool_choice: {"type": "auto"}`, the tool definition carries `strict: true` (the SDK's
   `ToolParam.strict`, anthropic 0.107.0), and the user content ends with one instruction line:
   „Answer only by calling the tool `<tool>` with the complete result; do not reply in text.“
   The system prompt is untouched (its pin and its cache stay).
3. A response without the tool's `tool_use` block is, in auto mode, a **retryable** failure
   inside the existing budget (the model answered in text); in forced mode it stays the terminal
   error it is today. Truncation handling is unchanged in both modes.
4. `ForcedToolCaller(model, …, forced=None)` reads the setting when `forced` is not given, so
   every agent follows the switch without a signature change.

## 3 Guards before the change

1. Forced mode (default): the request kwargs carry `tool_choice` of type `tool`, no `strict`, the
   user content unchanged.
2. Auto mode: `tool_choice` is `auto`, `tools[0]["strict"]` is `True`, the user content ends with
   the instruction naming the tool; everything else identical.
3. Auto mode: a text-only answer followed by a tool answer succeeds in two calls with one sleep;
   text on every attempt exhausts the budget as `LLMCallError`.
4. `Settings.forced_tool_choice` defaults to `True`; `FORCED_TOOL_CHOICE=false` turns it off.

## 4 Pre-registration

The twelfth chain (WP59) runs with `FORCED_TOOL_CHOICE=false` on Sonnet 5.5 / Opus 5.5: every
call returns the tool block (zero text-only retries is the hope; the count is reported from the
trace's `llm_error` events with „no tool_use block“).

## 5 Not in this WP

Structured outputs as an alternative; detecting the restriction from the model id (a config
switch, not a name heuristic); the Bedrock/Vertex routes' behaviour under `auto`.

## 6 Results

*(appended after the change)*
