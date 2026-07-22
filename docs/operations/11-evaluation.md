# 11. Evaluation & release operations

This chapter is the maintainer's half of the manual: how quality is measured, and what
must happen before a model bump, a prompt change, or a rules change ships.

## 11.1 The eval harness

Three strictly separated layers under `eval/`. **Golden datasets**
(`eval/datasets/<case>/dataset.yml`) pair an input document (or a synthetic
`generate:` block for the scale cases) with the expected model and optional
`min_scores` gates — `bank` is the high-floor reference (Postgres-verified model),
`health_insurance` the walkthrough case, `messy_insurance` the deliberately cryptic
trap set (ungated canary), `scale_30/100/300` the synthetic scale series.
**Deterministic scorers** (`eval/scorers.py`) match structurally (normalised
identifiers, never string luck) and are pinned by keyless tests. The **live runner**
executes the real graph:

```bash
uv run python -m eval.run --dataset bank --repeat 3     # or --all
```

Each repeat auto-resumes the checkpoint (like `resume --accept`), is scored, and is
written to `eval/results/<case>/<timestamp>-run<N>.json` **immediately** — a crash or
credit exhaustion mid-batch keeps every completed repeat on disk, prints an incomplete
banner, and exits non-zero. The summary reports mean/min/max per scorer across
repeats; a mean below a case's `min_scores` exits 1. This is a **manual pre-release
gate** — deliberately not CI (live runs cost tokens and need a key).

## 11.2 Scorers & metrics

Model-quality scorers: `construct_f1` (structural hub/link/sat match against the
golden model), `driving_key_accuracy`, `validation_gate` (the run's own gates pass),
`pipeline_health`. Mapping scorers come in two per-case modes: `concept` (name-aligned
goldens — precision/recall on concept-keyed mappings, gap detection, confidence
calibration) and `column` for the scale cases, where naming diverges by construction
(`mapping_coverage` — recall over golden column pairs — plus the gateable
`false_friend_hits`; concept-coupled scorers are reported but not gateable there).

Every result JSON also carries a `metrics` block — token usage, wall clock,
review-queue size, construct/flag counts, `backstop_fires`, `trace_path` — and the
full mapping proposal dump, so a regression can be read concept-by-concept from the
artifacts without re-running.

## 11.3 When to run what

After a **prompt or rules change**: the affected gated cases, `--repeat 3` (variance
is real; single runs mislead). Before a **release**: all gated cases green. After a
**model bump**: the full protocol below, ablation first. The scale cases are
measurement instruments, not gates — run them when input size or cost behaviour is
the question, with the budget/abort criteria in
`docs/architecture/scale-test-findings.md`, which also sets the evidence rule: quote
the trace, don't file hunches.

## 11.4 Model-release protocol: ablation & the steering ledger (WP16)

The steering registry (2.3, 8.3) makes prompt-compensation measurable. On a model
bump, ask "does the new model still need each crutch?" empirically:

```bash
uv run python -m eval.ablate --case health_insurance --drop cdk_not_payload \
    [--model <candidate-id>] [--repeat N]
```

The runner executes a **baseline arm** and a **rule-dropped arm** on the real graph
and records, per arm: scores, validation issue codes, backstop fires, and usage — the
comparison JSON under `eval/results/ablation/` is rewritten after every completed
repeat (crash-safe), and a two-column summary is printed.

Decision rule (from `docs/architecture/steering-ledger.md`, where every rule's
inventory, evidence, and verdict live): a rule whose dropped arm shows **zero backstop
fires and no gated-score regression across N ≥ 3 repeats** becomes `candidate-delete`
— a human decides. Prompt text is cheap to revert; deleting a *backstop* additionally
requires that its E_-gate stays (the gate catches the failure if the deletion was
premature). The boundary never moves: **validator gates are the product and are never
ablated** (8.3). Start each protocol run with the cheap, high-signal subset — gated
cases × rules that have a linked backstop.

## 11.5 LangSmith upload (optional)

With `LANGSMITH_API_KEY` set and the `eval` extra installed, live eval runs create one
LangSmith dataset per case and log each run with its scores as feedback — useful for
comparing runs across time in a UI. Without key or package the layer is a silent
no-op; nothing else in the project talks to LangSmith.
