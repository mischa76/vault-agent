# 10. Observability & debugging

## 10.1 Logging: `--debug`

Default console output is the curated run narrative (plan, progress, summary,
checkpoint). The global `--debug` flag — before the subcommand: `vault-agent --debug
run …` — switches on DEBUG logging including the library's module loggers (agent-run
boundaries with construct counts, payload sizes) and re-raises pipeline failures with
the full traceback instead of the one-line summary. The CLI is the only place logging
is configured; there is no logging setting to manage.

## 10.2 LLM traces (WP15)

Every run writes a transcript of its LLM interactions:
`.vault-agent/traces/<thread_id>.jsonl`, one JSON object per event, default **on**
(`--no-trace` opts out). A resume appends to the same file, so one HITL run reads as
one transcript; a crash keeps everything written so far.

Event kinds: `llm_call` (a completed API response — including a truncated one),
`llm_error` (a terminal failure: truncation, missing tool block, exhausted retries, a
non-retryable 4xx), and `backstop` (10.4). Fields per event: timestamp, `tool_name`
(the de-facto agent id — e.g. `emit_dv_model` is the modeler), `model`, `attempt`,
`system_prompt` + `system_prompt_sha` (full text only on the first event per sha —
later events carry the sha alone), `user_content`, `max_tokens`. Every `llm_call`
additionally carries the tool `payload`, `stop_reason`, and token usage — including a
truncated one (`stop_reason: "max_tokens"`, and the tokens it was billed for); on a
response without the forced tool block the `payload` is `null`.

Handle with care: traces contain the **raw document and source text**. They live only
under `.vault-agent/` (git-ignored) and are not demo-safe — never publish one.

## 10.3 Reading a trace

The discipline (LOOPS.md rule VII, adopted via WP15): when a run made a strange
decision, don't re-run with prints — grep the transcript for the moment the model's
judgment diverged, and cite `tool_name`/`attempt` when filing a finding. Recipes
(`jq` optional but worth it):

```bash
T=output/.vault-agent/traces/<thread>.jsonl   # 'output' = the --out dir of the run

jq -r '.kind + "  " + .tool_name + "  attempt=" + (.attempt|tostring)' $T   # overview
jq 'select(.tool_name=="emit_dv_model")' $T                # the modeler call(s), full payload
jq 'select(.tool_name=="emit_dv_model") | .payload.satellites' $T   # just its satellites
jq 'select(.kind=="llm_error")' $T                         # what failed, and how
jq 'select(.kind=="backstop")' $T                          # what was silently repaired
jq -s 'map(select(.kind=="llm_call") | .input_tokens) | add' $T   # input-token total
```

The most useful comparison in practice: the modeler's attempt-1 vs attempt-2 payloads
after a validation failure — it shows exactly what the error feedback did (and did not)
change.

## 10.4 Backstop events

Three deterministic pre-gate repairs announce themselves as `kind: backstop` events
*when and only when they actually repaired something*: `attributes_without_cdk` (a CDK
was also listed as payload — dropped attrs in the detail), `fk_demotion` (a business
key's FK occurrence was demoted to its anchor table), `effsat_two_attributes` (an
effectivity satellite with ≠2 attributes was rejected into a generation-gap flag).

For the **operator** a fire is informational — the model needed a known crutch, the
output is already correct; nothing to do. For the **maintainer** the fires are the
telemetry behind the model-release protocol (11.4): a model that stops triggering a
backstop makes its steering rule a deletion candidate.

## 10.5 Cost & usage

Per-call token usage (input, output, cache reads) is recorded on every `llm_call` trace
event — `llm_error` and `backstop` events carry zeros, so filter on `llm_call` when
totalling a run by hand; eval runs additionally aggregate it into their result metrics
(11.2). What keeps costs predictable: system prompts are cache-controlled (retries and
per-asset contract calls hit the cache), re-model feedback sends errors only, and
oversized documents are cut and flagged rather than ballooning silently. The expensive
step is the modeler (heavy model); a run that loops all three modeling attempts costs
roughly three modeler output generations on a cached prompt.

## 10.6 `.vault-agent/` internals

| Entry | Lifecycle |
|-------|-----------|
| `checkpoints.sqlite` | LangGraph checkpointer, one thread per run. Thread pruned on finalization; kept while paused. Does not grow unboundedly. |
| `pending.json` | Written on pause (thread id + input doc); cleared on finalization. Its presence is what `resume` looks for. |
| `traces/<thread>.jsonl` | One per run thread; append-only; never auto-deleted. |

Safe to delete the whole directory when: no paused run you still care about, and no
trace you still need. Deleting it never touches the deliverables — it only forfeits
resume-ability and history.
