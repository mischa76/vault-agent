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

Shipped cases: `bank` (the Postgres-verified end-to-end PoC model; gated), `health_insurance`
(from the demo walkthrough), `messy_insurance` (grounded messy German Fachkonzept; loose,
ungated — exists to catch review-queue/grounding regressions). Golden-model choices and
their rationale are documented as comments inside each `dataset.yml`.

## Scorers (all 0..1, deterministic)

- **construct_f1** — mean F1 of generated vs golden constructs over the three kinds.
  Hubs match on normalised name + business key, satellites on normalised name + parent +
  `sat_type` (+ the normalised attribute set when the golden lists attributes). **Links
  match on their *grain*** — the sorted multiset of participating hubs (ADR-0009 roles
  collapsed to their hub) — *not* on the name, because the name is free-form modeller
  output: `link_policy_insured_person` and `link_insured_person_policy` are one construct.
  The name only breaks a tie when two generated links share a grain (which the validator
  flags as `W_LINK_REDUNDANT_GRAIN`); an unresolvable tie stays unmatched rather than
  guessing. Extras and misses both cost score (precision/recall) **within a kind the
  golden declares**; a kind the golden says nothing about is excluded from the mean, not
  scored 0.0 — see the vacuity note below.
- **driving_key_accuracy** — fraction of golden links with declared driving keys whose
  generated counterpart declares the same normalised set; 1.0 when the case declares none.
  The counterpart is resolved on grain, as for `construct_f1`.

> **Vacuity — one convention for every scorer: nothing to check ⇒ score 1.0 and `details`
> starting with `vacuous — `.** An empty golden makes no claim, so generating constructs
> against it is not a failure: before 2026-07-28 `construct_f1` returned **0.000** for the
> synthetic `scale_*` cases (which ship a golden *mapping* and no golden *model*), which
> reads as total failure and means "nothing was checked". `confidence_calibration` had the
> same defect mirrored (0.0 for "no scored proposals") until WP18; every nothing-to-check
> branch now carries the prefix (`scorers.VACUOUS_PREFIX`).
>
> **A vacuous score can never satisfy a gate**, enforced twice:
> - `load_eval_case` rejects a case gating `construct_f1`/`driving_key_accuracy` while its
>   golden model declares nothing for them (cheap, at load time);
> - the runner rejects, after scoring, any gated scorer that was vacuous in **every** repeat
>   — `GATE UNSATISFIABLE`, exit 1. This is the only check that can see the golden *mapping*,
>   which the loader never opens.
>
> A gated scorer that produced **no score at all** — a typo'd name in `min_scores`, or a
> missing `golden_mapping.yml`, which makes the runner skip the whole mapping family — is the
> same defect and gets the same `GATE UNSATISFIABLE` + exit 1. A gate must fail loudly on
> absence of evidence, never pass on it.

> **Caveat — hubs and satellites are still name-keyed.** `normalize_identifier` folds
> casing and separators but not word order, so a golden hub/satellite whose name the
> modeller words differently scores as a miss even when the construct is right. This is
> only safe where the golden and the modeller agree on naming (the hand-written cases);
> for a synthetic golden it is not, which is one reason the `scale_*` cases gate on
> mapping scorers rather than on `construct_f1`.
- **validation_gate** — 1.0 iff the run's validation outcome matches
  `expectations.validation_passed` and the warning count stays within
  `max_validation_warnings` (when set); else 0.0 with details.
- **pipeline_health** — 1.0 iff no `PipelineFlag` with `severity == "error"` was raised.
- **existing_construct_preservation** (WP23) — for a brownfield case (`existing:` in
  `dataset.yml`), the share of the extended vault's constructs that survived the run
  unchanged: not removed, not re-keyed, payload not reshaped. This is the promise the
  extension mode makes, so it is gated at exactly **1.0** — anything less is a defect,
  not a quality signal. It deliberately re-measures what the validator's `E_EXISTING_*`
  gates enforce: an eval scorer checks the OUTCOME, because the mechanism could itself
  be wrong. Vacuous (1.0, prefixed) on greenfield cases, and `load_eval_case` refuses to
  let one gate it.

### Mapping scorers (WP9)

Score a run's `state.mappings` (a `ProposedMapping`) against a case's optional
`golden_mapping.yml` (loaded by `eval/mapping.py`). All three match structurally through
`normalize_identifier` on concept/table/column.

- **Golden concept universe** (WP9.2) — the concepts a golden mapping actually judges:
  every concept in `mappings` + `gaps` + `ambiguous`. The live pipeline maps the *generated*
  model's concepts, which routinely include constructs the golden set does not cover (the
  bank modeler adds transactions/addresses). `mapping_accuracy` and `confidence_calibration`
  score **only** proposals whose concept is in this universe; out-of-universe proposals are
  reported (`"N proposals outside the golden universe, unscored"`), never penalised.
- **mapping_accuracy** — F1 of the scored `concept → (table, column)` proposals. Precision
  denominator = scored proposals; recall over the mappable concepts (`mappings` +
  `ambiguous`, any `ambiguous` candidate correct). A force-fit of a `gap` concept or a
  false-friend column still costs score (both are in the universe).
- **gap_detection** — recall over the golden `gaps` (fraction correctly called a gap). The
  force-fit penalty (a golden gap mapped anywhere) stays **global** — it considers all
  proposals, by design.
- **confidence_calibration** (informational) — margin = mean confidence of correct scored
  proposals − mean of wrong ones. With **no wrong proposals** to separate from, the margin
  is **1.0** by definition (perfect separation), not the mean confidence; with **no scored
  proposals at all** the verdict is vacuous (1.0 + prefix, see the vacuity note above).

#### Matching mode: `concept` vs `column` (WP14)

A case declares `mapping_match: concept` (default) or `mapping_match: column` in its
`dataset.yml`; the runner picks the mapping scorers accordingly.

- **`concept`** (default) — the scorers above (`mapping_accuracy`, `gap_detection`,
  `confidence_calibration`), keyed on the proposal's *concept* name. Correct for the
  name-aligned goldens (`bank`, `messy_insurance`), whose golden concepts match the
  pipeline's actual concept vocabulary.
- **`column`** (the scale cases) — the synthetic scale goldens sample their *own* concept
  vocabulary, while the mapper's concepts are the modeler's free-form hub-key/attribute
  names; at 30 tables they diverge almost entirely, so concept-keyed `mapping_accuracy`
  measured naming alignment, not mapping quality (a healthy pipeline failed the gate 3/3 —
  `../docs/architecture/scale-test-findings.md` Candidate #2). Column mode instead runs:
  - **mapping_coverage** — pair-based recall: the fraction of golden mappable entries whose
    `(source_table, source_column)` pair is bound by *some* proposal (an `ambiguous` entry
    by any candidate). No concept/entity coupling and no synthetic precision/F1 — it scores
    the mapper's actual job, column binding. The statistics trap survives (binding the
    shadow GUID is a different pair → miss); proposals binding a column outside the golden
    set are reported, never penalised.
  - **false_friend_hits** — gateable guard: **1.0** when no proposal binds a golden
    `false_friends` pair, else **0.0** (hits named). Lets the review gate "coverage ≥ 0.8
    **and** zero false-friend hits" be two `min_scores` lines.
  - **gap_detection** — still computed but **reported-only** (its details are prefixed
    `concept-coupled — reported only in column mode`): both gap recall and the force-fit
    check key on the concept name, so they are blind at scale. The loader **rejects** a
    column-mode case whose `min_scores` gates a concept-coupled scorer
    (`mapping_accuracy`/`gap_detection`/`confidence_calibration`). The scale gap signal is
    the reported gap/unresolved counts plus a human spot-check of the proposal dump.

Every result JSON (both modes) carries a `mappings` block — `state.mappings.model_dump()`
(proposals + gaps + unresolved) — so a single scale re-run can be inspected
concept-by-concept.

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
- Each repeat also writes its **LLM transcript** next to the result JSON
  (`<timestamp>-run<i>.trace.jsonl`, WP15) — one JSON object per API call with the system
  prompt (once per digest), the user payload, and the tool payload returned. The result's
  `metrics` block carries `trace_path` plus `backstop_fires` (WP16: `{backstop_id: n}`,
  counted only when a deterministic repair actually fired).

## Ablation runner (WP16)

Measures whether a modeler steering rule is still needed by the current model: it runs a case
once **baseline** and once with one `SteeringRule` dropped from the prompt, and compares
scores, validation issue codes, backstop fires and usage.

```bash
uv run python -m eval.ablate --case health_insurance --drop cdk_not_payload --repeat 3
uv run python -m eval.ablate --case bank --drop unit_of_work --model <candidate-model>
```

One comparison JSON per invocation under `eval/results/ablation/` (rewritten after every
completed repeat, so a mid-run failure never discards a paid-for arm). Rule ids come from
`vault_agent.rules.dv2_rules.DV_MODELING_RULES`; the exclusion seam is never used by
production code. Verdicts belong in `docs/architecture/steering-ledger.md` — the runner
measures, a human decides, and validator gates are never ablated.

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
