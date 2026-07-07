# Eval harness (WP6)

Measures whether a prompt change, model upgrade, or rules tweak makes the LLM agents
better or worse. Spec: `docs/architecture/backlog-2026-07/wp6-eval-harness-spec.md`.

Three strictly separated layers:

| Layer | Where | Needs |
|---|---|---|
| 1 — golden datasets | `eval/datasets/<case>/dataset.yml` + loader `eval/datasets.py` | nothing (keyless, CI-tested) |
| 2 — deterministic scorers | `eval/scorers.py` | nothing (keyless, CI-tested) |
| 3 — live runner | `eval/run.py` | `ANTHROPIC_API_KEY` (real LLM calls) |
| optional — LangSmith | `eval/langsmith_upload.py` | `LANGSMITH_API_KEY` + the `eval` extra |

The default test suite (`uv run pytest -q`) never runs layer 3 and never needs the
`langsmith` package.

## Dataset format

One directory per case under `eval/datasets/`, containing a `dataset.yml`:

```yaml
name: bank                        # unique id (= result/LangSmith dataset key)
input_document: ../../../examples/inputs/bank_account_requirements.md  # rel. to this file
source_schema: ../../../examples/inputs/bank_source_schema.yml         # optional (grounded)
golden:
  hubs:
    - {name: hub_customer, business_key: national customer ID}
  links:
    - {name: link_account_customer, connected_hubs: [hub_account, hub_customer],
       driving_key: [hub_account]}                 # driving_key optional
  satellites:
    - {name: sat_customer_details, parent: hub_customer, sat_type: standard}
      # attributes: [...] may optionally be listed -> then compared as a normalised set
expectations:
  validation_passed: true
  max_validation_warnings: 8      # tolerance, not exactness; omit to skip the check
  min_scores:                     # optional: the runner exits 1 when a MEAN falls below
    construct_f1: 0.5
```

Golden matching is **structural, never textual**: every name/key/set is compared through
`rules.normalize_identifier`, so `national customer ID` matches `NATIONAL_CUSTOMER_ID`.
Malformed files raise an attributable error naming file and problem (same contract as
`source_schema.load_source_schemas`).

Shipped cases: `bank` (the Postgres-verified Durchstich model; gated), `health_insurance`
(from the demo walkthrough), `messy_insurance` (grounded messy German Fachkonzept; loose,
ungated — exists to catch review-queue/grounding regressions). Golden-model choices and
their rationale are documented as comments inside each `dataset.yml`.

## Scorers (all 0..1, deterministic)

- **construct_f1** — mean F1 of generated vs golden constructs over the three kinds.
  Hubs match on normalised name + business key, links on normalised name +
  connected-hub *set*, satellites on normalised name + parent + `sat_type` (+ the
  normalised attribute set when the golden lists attributes). A kind that is empty on
  both sides is vacuous (1.0); extras and misses both cost score (precision/recall).
- **driving_key_accuracy** — fraction of golden links with declared driving keys whose
  generated counterpart declares the same normalised set; 1.0 when the case declares none.
- **validation_gate** — 1.0 iff the run's validation outcome matches
  `expectations.validation_passed` and the warning count stays within
  `max_validation_warnings` (when set); else 0.0 with details.
- **pipeline_health** — 1.0 iff no `PipelineFlag` with `severity == "error"` was raised.

## Live runner

```bash
uv run python -m eval.run --dataset bank            # one case, 3 runs (default)
uv run python -m eval.run --all --repeat 5
uv run python -m eval.run --dataset bank --out eval/results
```

- Requires `ANTHROPIC_API_KEY` (exit 2 with a clear message otherwise).
- Runs the real graph per repeat (in-memory checkpointer). The human-in-the-loop
  checkpoint is auto-resumed like `vault-agent resume --accept` with no owners assigned,
  so runs complete unattended; the unassigned owners still surface as flags.
- Per run, one JSON result is written to
  `eval/results/<case>/<UTC-timestamp>-run<i>.json` (scores, per-scorer diff details,
  model ids from `get_settings()`, git SHA). `eval/results/` is git-ignored.
- The console table shows mean/min/max per scorer across the repeats — repeat runs are
  how LLM variance becomes visible.
- Exit code 1 when any scorer's **mean** falls below the case's `expectations.min_scores`
  threshold: a manual pre-release gate. No CI wiring (cost decision deferred, spec §7).

## LangSmith (optional)

With `LANGSMITH_API_KEY` set (see `config.Settings.langsmith_api_key`) **and** the
`langsmith` package installed (`uv sync --extra eval`), the runner additionally

1. creates one LangSmith dataset per eval case (`vault-agent-eval-<case>`, with the
   golden model as example), and
2. logs each live run with its scores attached as feedback.

Absence of the key or the package changes nothing — the import is guarded and the upload
is skipped. To also trace the pipeline's internal LLM calls in LangSmith, export the
standard LangChain tracing variables before running (documented, not code-enforced):

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=$LANGSMITH_API_KEY
export LANGCHAIN_PROJECT=vault-agent-dev   # settings.langsmith_project
```
