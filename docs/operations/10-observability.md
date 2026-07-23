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
judgment diverged, and cite `tool_name`/`attempt` when filing a finding. Recipes below
use `jq` (the WSL install script brings it; otherwise `apt install jq` — or use the
jq-free variants further down):

```bash
T=output/.vault-agent/traces/<thread>.jsonl   # 'output' = the --out dir of the run

# overview — exactly one of tool_name / backstop_id is set per event, so they concatenate
jq -r '"\(.kind)  \(.tool_name + .backstop_id)  attempt=\(.attempt)"' $T
jq 'select(.tool_name=="emit_dv_model")' $T                # the modeler call(s), full payload
jq 'select(.tool_name=="emit_dv_model") | .payload.satellites' $T   # just its satellites
jq 'select(.kind=="llm_error")' $T                         # what failed, and how
jq 'select(.kind=="backstop")' $T                          # what was silently repaired
jq -s 'map(select(.kind=="llm_call") | .input_tokens) | add // 0' $T   # input-token total
```

**Without jq.** Hardened environments often cannot install tooling. The same views work
with the Python standard library alone — no jq, no dependencies, and no project
virtualenv (a trace is plain jsonl; reading one needs nothing from vault-agent):

```bash
P='import json,sys; rows=[json.loads(l) for l in open(sys.argv[1])]'

python3 -c "$P
for e in rows:
    print(e['kind'], e['tool_name'] + e['backstop_id'], 'attempt', e['attempt'])" $T

python3 -c "$P
for e in rows:
    if e['tool_name'] == 'emit_dv_model':
        print(json.dumps(e['payload']['satellites'], indent=2))" $T

python3 -c "$P
for e in rows:
    if e['kind'] == 'llm_error':
        print(e['error'])" $T

python3 -c "$P
print(sum(e['input_tokens'] for e in rows if e['kind'] == 'llm_call'))" $T
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

## 10.7 The data boundary: what leaves the machine

The short version for a compliance conversation: **row-level data processing happens
exclusively in your warehouse, through generated dbt/AutomateDV SQL.** The pipeline
never connects to the warehouse — it generates code, dbt executes it. No Python process
and no LLM ever reads a row from your tables *itself*; this is architectural (there is
no warehouse connection in the pipeline to begin with, and it does not invoke dbt
either), not a configuration promise. What it sees of your data is exactly what you put
in front of it — which is the next paragraph.

What **does** go to the Anthropic API is the pipeline's three inputs: the requirements
document (in full — including any real data examples someone pasted into it), the
declared source schema (metadata: table/column names, types, comments), and the
profiling evidence. Profiling is the one deliberate touchpoint with data *values*: its
**example values** are genuinely useful mapping evidence, but against real source
systems they are real values (account numbers, partner names). If that is not
acceptable, omit or mask the example values — the mapper then works from names, types,
comments, and the statistical shape alone, at some cost to mapping confidence
(structural evidence still carries most of the signal; the opacity-probe measurements
in the WP9 record quantify the degradation).

Everything else stays local: traces (10.2) persist exactly the API-bound material to
disk and nothing more; checkpoints, reports, and artifacts never leave the machine;
LangSmith upload (11.5) is off unless explicitly configured, and even then carries
eval scores and run metadata, not source data. For the test and demo runs shipped with
the repo, all inputs are synthetic — the boundary question only becomes real when you
point the pipeline at real systems.
