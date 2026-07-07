# WP6 — Eval harness: golden datasets, deterministic scorers, optional LangSmith layer

Status: Proposed · Size: M/L · Depends on: WP4 · Enables: safe prompt/model iteration

## 1. Problem

`eval/` is empty scaffolding; `langsmith` is a declared-but-unused extra. There is no way
to measure whether a prompt change, model upgrade, or rules tweak makes the LLM agents
better or worse. For an LLM product this is the biggest missing quality instrument
(project review 2026-07-06, item 10). CLAUDE.md names LangSmith evals as the declared next
milestone.

## 2. Architecture: three layers, strictly separated

```
eval/
  datasets/<name>/dataset.yml     # input + golden expectation (layer 1: data)
  scorers.py                      # pure scoring functions   (layer 2: deterministic)
  run.py                          # live runner + reporting   (layer 3: needs API key)
  langsmith_upload.py             # optional: push runs/datasets to LangSmith
```

Layers 1+2 are keyless and unit-tested in CI like everything else. Layer 3 runs the real
pipeline (real LLM calls) and is *never* part of the default test suite.

## 3. Layer 1 — dataset format [ENFORCE]

One directory per case under `eval/datasets/`. `dataset.yml`:

```yaml
name: bank                        # unique id
input_document: ../../examples/inputs/bank_requirements.md   # relative to dataset.yml
source_schema: ../../examples/inputs/bank_source_schema.yml  # optional (grounded run)
golden:
  hubs:
    - {name: hub_customer, business_key: national customer ID}
    - {name: hub_account,  business_key: account number}
  links:
    - {name: link_account_customer, connected_hubs: [hub_account, hub_customer],
       driving_key: [hub_account]}
  satellites:
    - {name: sat_customer_details, parent: hub_customer, sat_type: standard}
    - {name: sat_account_customer_eff, parent: link_account_customer,
       sat_type: effectivity}
expectations:
  validation_passed: true
  max_validation_warnings: 8      # tolerance, not exactness
```

Typed loader (`eval/datasets.py` or inside `run.py`): pydantic models `GoldenModel`,
`EvalCase`; malformed YAML → attributable error naming file + field (mirror
`source_schema.load_source_schemas` style). Golden matching is *structural*, not textual:
names and keys are compared through `rules.normalize_identifier`; satellite attribute
*sets* may optionally be listed and are then compared as normalised sets.

Initial cases: `bank` and `health_insurance` (from `docs/demos/` inputs), plus
`messy_insurance` (the grounded messy run from `examples/inputs/messy_insurance_*`) with
looser expectations (this case exists to catch review-queue regressions).

## 4. Layer 2 — deterministic scorers (pure functions, keyless tests)

`eval/scorers.py`, each `(state: VaultAgentState, case: EvalCase) -> ScorerResult`
(`ScorerResult`: `name`, `score: float 0..1`, `details: str`):

- `construct_f1`: precision/recall/F1 of generated vs golden constructs, matched on
  normalised `(kind, name)`; hubs additionally require the normalised business key to
  match, links the normalised connected-hub *set*, satellites the parent + sat_type.
  Score = mean F1 across the three construct kinds.
- `driving_key_accuracy`: fraction of golden links with declared driving keys whose
  generated counterpart declares the same normalised set. No golden driving keys → 1.0.
- `validation_gate`: 1.0 iff `expectations.validation_passed` matches and warning count
  ≤ `max_validation_warnings`, else 0.0 with details.
- `pipeline_health`: 1.0 iff no `PipelineFlag` with `severity == "error"`, else 0.0.

Unit tests build synthetic states + golden specs and pin exact scores, including partial
matches (e.g. 2 of 3 hubs → known F1 value).

## 5. Layer 3 — live runner

`uv run python -m eval.run --dataset bank [--all] [--repeat N] [--out eval/results/]`:

1. Requires `ANTHROPIC_API_KEY`; exits with a clear message otherwise.
2. Runs the *real* graph (same entry as `cli._run_pipeline`, MemorySaver is fine) on the
   case's inputs; `--repeat N` (default 3) reruns to expose LLM variance.
3. Applies all scorers; writes one JSON result per run
   (`results/<dataset>/<timestamp>.json`: scores, model ids from `get_settings()`,
   git SHA, per-run construct diff details) and prints a compact table (mean ± min/max
   per scorer across repeats).
4. Exit code 1 if any *mean* score falls below a per-case optional
   `expectations.min_scores: {construct_f1: 0.8, ...}` — usable as a manual pre-release
   gate. No CI wiring in this WP.

## 6. LangSmith layer (optional, last)

`eval/langsmith_upload.py`: if `LANGSMITH_API_KEY` is set, (a) create/update a LangSmith
dataset per eval case, (b) log each live run with its scores as feedback. Guard every
import (`langsmith` stays an optional extra). Wire `settings.langsmith_*` from `config.py`
(coordinate with WP5 §5.3 — the fields stay). Tracing of the pipeline itself
(LANGCHAIN_TRACING_V2) is documented in `eval/README.md` but not code-enforced.

## 7. Out of scope

CI-scheduled eval runs (cost decision for later); prompt-optimisation tooling;
contradiction-detection metrics (needs reality-test #1 design first).

## 8. Acceptance criteria

1. `pytest` stays keyless-green: dataset loader + all scorers fully covered.
2. `python -m eval.run --dataset bank` performs a real run and emits scores + JSON
   (verified once manually with a key; paste the output into the PR description).
3. Repeat runs expose variance in the report (mean/min/max visible).
4. LangSmith upload is import-guarded; absence of the key/package changes nothing.
5. `eval/README.md` documents dataset format, scorer semantics, runner usage. Standard DoD.
