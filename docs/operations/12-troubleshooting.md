# 12. Troubleshooting & FAQ

## 12.1 Pipeline failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `LLMCallError: … response truncated at max_tokens=…` | A tool payload exceeded its output budget. The known wide-schema case (contract enricher) is fixed by chunking (2026-07-15); a new occurrence means a genuinely oversized single payload. | Check the trace for which tool; shrink the input (split the document) or file it — the per-call budgets are code constants. |
| `Pipeline failed: … 400 …` mid-run (often `credit balance`) | Non-retryable API error — exhausted Anthropic credit is the classic. Deliberately not retried. | Top up / fix the key; the run is on disk — a *paused* run resumes, a failed one re-runs (contracts/prompts are cached, but LLM stages re-execute). The trace's `llm_error` event names the failing call. |
| Run ends failed after *attempt 3/3* | The model couldn't produce a gate-clean model within the retry budget. | Read `report.html` + the review queue: recurring `E_` codes point at the requirements (ambiguous entities, relationship soup). Improve the document or ground with a schema; chapter 8 has per-code guidance. |
| `INPUT_TRUNCATED` advisory flag | Document longer than 400k chars; pipeline continued on the head. | Usually fine for prose docs; for inventory-style docs, split or slim the input. |
| `Could not load an input file: …` | Malformed `--source-schema`/`--profiling` (the loaders name file and problem). | Fix the named entry; the error is attributable by design — no LLM tokens were spent. |
| `could not read <doc>: …` error flag | The document exists but is unreadable (non-UTF-8 text, corrupt PDF/`.docx`). | The file was skipped, not fatal: re-save it as UTF-8 / repair the document. A single-document run then has nothing to parse and fails attributably. |
| Rate-limit / 5xx noise in `--debug` logs | Transient API failures. | Nothing — retried 3× automatically; only exhaustion surfaces as `LLMCallError`. Each wait is logged at INFO with its length and where it came from: a server `Retry-After` header wins (capped at 60 s), otherwise exponential backoff with equal jitter so parallel runs stop colliding. |

## 12.2 Checkpoint & resume issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No unfinished run found under <out>/` | Nothing paused or crashed there: wrong `--out`, already finalized, or `.vault-agent/` deleted. | Point `--out` at the run's output dir; check for `pending.json` under `<out>/.vault-agent/`. |
| `Cannot read the unfinished-run pointer: …` | `pending.json` exists but is truncated, not JSON, or has no `thread_id` (usually a hand-edit or an interrupted write). | Repair the file, or delete it to abandon the run — the next `run` into that directory prunes the orphaned checkpoint thread. `--discard` cannot help here: it reads the same pointer. |
| `--existing`: `not a vault-agent output directory carrying metadata/dv_model.yml` | That output predates the logical-model dump (6.7). | Regenerate that vault once with the current version — the generator is deterministic, so the project is identical — then point `--existing` at the new output. |
| `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` | The satellite's `source_table` names a table that is not one of its multi-source parent's feeds (ADR-0011). | Name one of the feeds the message lists, to bind the satellite to that source system; or drop `source_table` if the attributes come from every feed. A finer-grain relation under one feed is not expressible today. |
| Extension run: many `W_EXISTING_EXTENDED` warnings | By design — one advisory per legitimate addition, so the review queue inventories the increment. | Nothing; read them as the changelog of the increment. |
| Pipeline failed mid-run — is the LLM work lost? | No (WP17): the crash writes a `crashed` `pending.json` and the artifacts-so-far. | `vault-agent resume --out <dir>` continues at the failed node; `--discard` throws the run away. |
| `The run failed again: …` on resume | A deterministic failure (corrupt input, a bug) repeats on every continuation. | Read the named error and the trace (chapter 10); fix the cause, or `resume --discard` and start over. |
| `resume` prints instructions instead of prompting | Non-TTY (pipe, CI) with no decision flags. | Use the flags (7.5) or force `--interactive` in a real terminal. |
| Paused run's `report.html` looks incomplete | By design — it shows the pending state. | Resume; finalization overwrites it. |
| Aborted the interactive prompt — is anything lost? | No: abort/skip/Ctrl-C keep `pending.json` and the checkpoint thread. | Resume again anytime. |
| Exit code 3, `The model did not validate after 3 modeling attempt(s)` | The re-model budget was exhausted with validation errors remaining; the run paused at the checkpoint for your decision (WP25). | Read the errors in `review-queue.md` / `report.html`. Fix the requirements or source schema and re-run; or `resume --accept` to keep the model for diagnosis (the ADR records that it was accepted over its errors); or `resume --discard`. |
| `resume --accept` succeeded but the command still exits 3 | By design: accepting does not make an invalid model valid, and the artifacts carry the known errors. | Nothing — treat exit 3 as "not deployable". A wrapper script should branch on it, not on the console text. |

## 12.3 dbt build failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Duplicate source table in `sources.yml` compilation error | Outputs generated before the 2026-07-14 dedup fix could list a relation twice. | Regenerate with the current version; the generator now merges by relation. |
| `column "…" specified more than once` on the eff_sat | Historic bug class, fixed via the dedicated `APPLIED_DTS` column. On current outputs this indicates a hand-edited staging model. | Regenerate; don't hand-edit staging (see FAQ). |
| Relation `raw_…` not found | Inferred binding (9.3) but no seed/table of that name. | Load seeds matching `sources.yml`'s expected columns, or ground + ratify so staging binds to your real tables. |
| Case/quoting errors on Postgres | An identifier got quoted somewhere — the whole pattern relies on unquoted UPPER_SNAKE folding. | Keep `quote_columns: false`; don't quote identifiers in hand-supplied seeds/tables. |
| Everything green, but incremental re-run changes counts | Not acceptable (9.2) — usually wrong staging grain or key duplication in the raw data. | Compare the first duplicated construct's staging against its source grain; check `W_MASAT_SHARED_GRAIN`-style advisories from the run. |
| AutomateDV version conflict on `dbt deps` | Version drift vs. the generated pin. | Keep the pin; bump only deliberately and re-run both demos as the regression gate. |

## 12.4 Environment issues

WSL performance: repo and venv belong on ext4, not `/mnt/c` (4.1). Missing extras
show up as import errors for dbt (`--extra demo`) or langsmith (`--extra eval`) —
`uv sync` with the right extra fixes both. Postgres auth failures are almost always
`profiles.yml` (host/port/role) rather than the generated project; the demos bundle a
working profile to compare against.

## 12.5 FAQ

**Can I run anything without an API key?** Everything except the LLM stages: the whole
test suite, both Postgres demos end-to-end, report/staging regeneration from a fixed
model, `--help`. `run`/`resume` and live evals need the key.

**Are warnings failures?** No. `W_` codes and advisory flags never block; they are the
pipeline being honest about what deserves your eyes (7.1). A run with 8 warnings and
no errors finalizes on `--accept`.

**Can I edit the generated SQL?** You can, but don't: regenerate instead. Hand edits
are lost on the next run, bypass the gates, and detach the output from its ADR trail.
The right lever is upstream — the requirements document, the schema declaration, or
the mapping ratification.

**Why did two runs on the same document differ?** The LLM stages are not
deterministic; the *deterministic* half (validation verdicts, generation from a given
model, the report) is. Judge a run by its gates and review queue, not by identity with
yesterday's run — and pin important models via the golden-dataset pattern (chapter 11)
if you need regression guarantees.

**How do I add a second source system for an existing hub?** Declare both systems in
the source schema, run grounded; a genuinely multi-source key lands in `unresolved`
with both candidates, and ratifying the `sources:` form (7.6) makes the hub
multi-source on the next generation.

**Where did my paused run go after a reboot?** Nowhere — it is on disk. `vault-agent
resume --out <dir>` from any shell.
