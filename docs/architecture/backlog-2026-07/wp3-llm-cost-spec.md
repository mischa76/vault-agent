# WP3 — LLM cost & robustness: prompt caching, slim retry feedback, input-size guard

Status: Proposed · Size: S · Depends on: — (coordinate §2.2 with WP4 if it lands first)

## 1. Problems (project review 2026-07-06, finding 3 remainder + parser edge)

1. No prompt caching: the modeler's system prompt (template + injected rules + optional
   grounding section) is byte-identical across up to `MAX_MODELING_ATTEMPTS` retries — on
   the heavy model that is the single largest avoidable cost.
2. Retry feedback is bulky: `dv2_modeler.run` feeds the *full* issue list (including
   warnings and long messages) back into the payload on re-model.
3. No input-size guard: `requirements_parser` sends whole documents as one message; a
   500-page PDF blows the context window with an opaque API error.

## 2. Target design [ENFORCE]

### 2.1 Prompt caching in the shared call path

One change point, all four agents benefit — `vault_agent/llm.py::ForcedToolCaller.call`:

```python
system=[{"type": "text", "text": system_prompt,
         "cache_control": {"type": "ephemeral"}}],
```

- Cache-eligibility floor: Anthropic requires ≥ 1024 tokens for caching on most models;
  shorter prompts are silently not cached — no conditional logic needed, always send the
  block form.
- The `tools` array is part of the cached prefix automatically (it precedes system in the
  prefix hash); no change needed there.
- Tests (`tests/test_llm.py`): assert the stub client received `system` as a one-element
  list whose block carries `cache_control == {"type": "ephemeral"}` and the prompt text.
  All existing behaviour tests must stay green unchanged.
- Verify against the current Messages API docs (`docs.claude.com`) before implementing —
  field names, not memory.

### 2.2 Errors-only retry feedback

In `dv2_modeler.run`, the re-model payload sends only blocking issues and only the fields
the model needs:

```python
errors = [i for i in state.validation_report.issues if <severity == "error">]
if errors:
    payload["previous_validation_issues"] = [
        {"code": ..., "construct": ..., "message": ...} for ... in errors
    ]
```

(Attribute vs. dict access depending on whether WP4 has landed.) Warnings are advisory for
humans, not steering input for the retry — sending them dilutes the correction signal and
costs tokens. Update `tests/test_agents/test_dv2_modeler.py`: the retry-feedback test pins
errors-only content and the absence of warnings/severity fields.

### 2.3 Input-size guard in the requirements parser

New constant in `rules/dv2_rules.py` is the wrong home (not a DV rule) — put it in
`agents/requirements_parser.py`:

```python
# Guard against blowing the model's context window: ~4 chars/token heuristic,
# capped well below the 200k window to leave room for system prompt + output.
MAX_DOCUMENT_CHARS = 400_000
```

New `FlagKind.INPUT_TRUNCATED = "input_truncated"` in `state.py`. In `_read_document`
(after successful extraction): if `len(text) > MAX_DOCUMENT_CHARS`, truncate to the limit
and `state.flag("requirements_parser", <message with original/truncated sizes and the
document path>, kind=FlagKind.INPUT_TRUNCATED, asset=doc_path)` — advisory severity
(pipeline continues on the head of the document; the human decides whether that is
acceptable). Never silently truncate: the flag is the point.

Tests: an oversized synthetic document is truncated, flagged with the right kind/asset,
and the extractor receives exactly `MAX_DOCUMENT_CHARS` characters; a normal document
produces no flag.

## 3. Explicitly out of scope

- Chunked multi-call extraction for huge documents (map-reduce parsing) — separate design,
  needs eval support (WP6) to validate quality.
- Caching across *processes/runs* (cache TTL strategy), batch API usage.

## 4. Acceptance criteria

1. Every Anthropic call sends the system prompt as a cache-controlled block; keyless test
   pins it.
2. Re-model payload contains only error-severity issues with exactly
   `code/construct/message`.
3. Oversized inputs are truncated + flagged (`INPUT_TRUNCATED`, asset = document path);
   normal inputs untouched.
4. Standard DoD.
