# WP15 — LLM trace capture: transcripts on disk, grep-able per run

Status: Proposed · Size: M · Depends on: nothing landed-after-WP14 (uses the WP13 §3
recorder seam pattern). Origin: Karpathy, *LOOPS.md* rule VII ("Read the traces") — every
debugging insight comes from reading the raw transcript, not from another experiment;
adaptation review 2026-07-22. WP16 depends on the recorder seam introduced here.

## 1. Problem

The pipeline's LLM interactions are invisible after the fact. `--debug` logs payload
*sizes*; LangSmith tracing is configured (`langsmith_tracing`) but nothing in the
pipeline emits to it; the eval harness records token *counts* (WP13 §3) but not content.
When a run mis-models (the CDK failure needed 4 live runs to diagnose; the WP9.1
FK-over-deferral was found by reading one transcript by hand), there is no artifact to
grep for the moment the model's judgment diverged. Diagnosis today means re-running with
ad-hoc prints — tuning by vibe, and each re-run costs tokens.

## 2. Design

### 2.1 Trace recorder seam (`src/vault_agent/llm.py`)

Mirror the WP13 `UsageRecorder` exactly: a `TraceRecorder = Callable[[TraceEvent], None]`
with a module-level default (`set_trace_recorder(recorder | None)`) plus a per-instance
ctor arg on `ForcedToolCaller` (tests). `TraceEvent` is a frozen dataclass (llm.py stays
pydantic-free):

- `kind: Literal["llm_call", "llm_error", "backstop"]` (`backstop` is reserved for WP16;
  this WP emits only the first two)
- `tool_name`, `model`, `attempt: int`
- `system_prompt_sha: str` and `system_prompt: str` — llm.py always fills both; dedup
  is purely a *writer* concern (2.2). The modeler's system prompt is byte-identical
  across retries by WP3 design, so deduping by sha keeps traces readable and small.
- `user_content: str`, `max_tokens: int`
- on success: `payload: dict[str, Any]`, `stop_reason: str | None`, usage numbers
- on `llm_error`: `error: str` (truncation, missing tool block, exhausted retries —
  fired from the same places `LLMCallError` is raised; a retryable attempt that will be
  retried is NOT an event, only the response/terminal outcome is)

Emission points: `_record_usage`'s call site (a completed API response — including a
truncated one, matching the usage semantics) and the three `LLMCallError` raise sites.
Same safety contract as the usage recorder: observational, recorder exceptions must
never disturb the call path (wrap, `logger.warning`).

### 2.2 Writer (`src/vault_agent/trace.py`, new)

`JsonlTraceWriter(path)` appends one JSON object per event (`\n`-delimited): ISO
timestamp, all event fields, with the system-prompt dedup (first occurrence per sha
carries `system_prompt`, later ones only the sha). Library code never configures where
traces go — the CLI does (WP5 §5.4 discipline).

### 2.3 CLI wiring (`cli.py`)

`run` and `resume` register a `JsonlTraceWriter` at
`<out>/.vault-agent/traces/<thread_id>.jsonl` (the checkpoint dir already holds per-run,
non-deliverable state; resume appends to the same thread's file, so one HITL run reads
as one transcript) and clear the recorder in `finally`. **Default ON** — a trace you
have to remember to enable is a trace you don't have when you need it; `--no-trace`
opts out. Traces are debug artifacts, not deliverables: they carry timestamps and are
exempt from the byte-identity determinism rules (report.html etc. unchanged); they also
carry document/source text, so they live only under `.vault-agent/` and the README notes
they are not demo-safe to publish (public-repo hygiene).

### 2.4 Eval wiring (`eval/run.py`)

Per repeat, register a writer at `eval/results/<case>/<timestamp>-run<N>.trace.jsonl`
(next to the result JSON, matching its `{timestamp}-run{run_index}.json` scheme,
git-ignored dir already); the result
JSON's `metrics` block gains `trace_path`. `docs/architecture/scale-test-findings.md`
gains a protocol line: before filing a finding, grep the trace for the diverging call
and cite the `tool_name`/`attempt` — findings quote transcripts, not hunches.

### 2.5 Out of scope

LangSmith as the trace backend (stays eval-upload-only; local files first — no new
dependency, no network requirement for debugging); a `vault-agent trace show`
pretty-printer (jsonl + grep/jq is the point; revisit only if the raw files prove
unreadable in practice); tracing non-LLM agent decisions (the decisions audit log
already covers those).

## 3. Tests (keyless)

In `tests/test_llm.py` via the existing stub client: success event carries
payload/stop_reason/usage; truncated response emits `llm_call` (usage semantics) then
`llm_error`; missing-tool-block and exhausted-retry paths emit `llm_error`; a raising
recorder never disturbs the call (result unchanged, warning logged); per-instance
recorder overrides the module default. In `tests/test_trace.py`: jsonl shape, append
across two writer sessions (resume case), system-prompt dedup by sha. In
`tests/test_cli.py`: run writes the trace file under `.vault-agent/traces/`;
`--no-trace` writes nothing; the recorder is cleared after the run (module default None).

## 4. Acceptance

1. A live run produces one grep-able jsonl transcript per thread; a paused+resumed run
   appends to the same file. Demonstrated on the bank demo: `grep emit_dv_model` finds
   the modeler call(s) with full payload.
2. Default CLI/console output unchanged; `--no-trace` restores today's behaviour
   byte-identically (no traces dir).
3. No behaviour change when no recorder is set (library import paths, keyless suite).
4. Suite green, ruff clean, mypy strict clean.
