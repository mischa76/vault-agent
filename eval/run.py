"""Live eval runner (wp6-eval-harness-spec.md §5) — layer 3, real LLM calls.

Runs the *real* pipeline graph (same entry shape as ``cli._run_pipeline``, but with an
in-memory checkpointer) on golden eval cases, applies every deterministic scorer, writes
one JSON result per run, and prints a compact mean/min/max table so repeat runs expose
LLM variance.

Never part of the default test suite: requires ``ANTHROPIC_API_KEY`` and exits with a
clear message without it. The pure helpers (aggregation, gating, payload building) are
keyless and unit-tested.

Usage::

    uv run python -m eval.run --dataset bank [--repeat 3] [--out eval/results]
    uv run python -m eval.run --all
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from eval.datasets import (
    DATASET_FILENAME,
    DATASETS_ROOT,
    GOLDEN_MAPPING_FILENAME,
    GOLDEN_RESOLUTION_FILENAME,
    EvalCase,
    load_all_cases,
    load_eval_case,
    materialize_case,
)
from eval.mapping import load_golden_mapping
from eval.resolution import load_golden_resolution
from eval.scorers import (
    ScorerResult,
    existing_construct_preservation,
    false_merge_rate,
    new_hub_detection,
    resolution_accuracy,
    resolution_calibration,
    score_mapping,
    score_state,
)
from vault_agent import llm
from vault_agent.agents.orchestrator import assemble_review_queue, render_review_queue_md
from vault_agent.cli import _checkpoint_serde
from vault_agent.config import get_settings
from vault_agent.existing_model import DV_MODEL_FILENAME, load_existing_model
from vault_agent.graph import build_graph
from vault_agent.llm import TraceEvent
from vault_agent.profiling import load_profiling
from vault_agent.rules.dv2_rules import canonical_hub_key_column
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import DVModel, VaultAgentState
from vault_agent.trace import JsonlTraceWriter

DEFAULT_REPEAT = 3
DEFAULT_OUT = Path("eval") / "results"

# The eval runs unattended: when the human-in-the-loop checkpoint interrupts (it usually
# does — generated contracts carry placeholder owners), resume exactly like
# ``vault-agent resume --accept`` with no owners assigned, so the run completes through
# the ADR author. Unassigned owners still show up as flags/review items and are scored.
#
# Since WP29's resolution checkpoint this ``accept`` has teeth beyond owners: at that pause it
# ratifies every proposed merge, so an unattended run models the resolver's proposals as if a
# human had agreed to them. That is deliberate — it is the configuration the arm comparison is
# about — but it is NOT the product's default posture, where a human answers that pause. A
# scorer reading ``false_merge_rate`` still reads the PROPOSALS, which this does not touch.
AUTO_RESUME_DECISION: dict[str, Any] = {"owners": {}, "accept": True}

# How many times one run may be resumed automatically. Two checkpoints can pause today (WP29's
# resolution checkpoint, then sign-off); the headroom is for a third without a code change,
# and the cap exists so a checkpoint the harness cannot answer fails loudly instead of looping.
_MAX_AUTO_RESUMES = 4


class ScoreStats(BaseModel):
    """Mean/min/max of one scorer across the repeats of one case."""

    mean: float
    min: float
    max: float


class UsageTotals:
    """Accumulates per-call token usage across a run (WP13 §3 cost transparency).

    Registered as the module-level ForcedToolCaller recorder for the duration of one run, so
    every agent's LLM call — the agents build their own callers — feeds the same totals."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.by_model: dict[str, dict[str, int]] = {}

    def record(self, model: str, input_tokens: int, output_tokens: int, cache_read: int) -> None:
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read
        per = self.by_model.setdefault(
            model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0}
        )
        per["calls"] += 1
        per["input_tokens"] += input_tokens
        per["output_tokens"] += output_tokens
        per["cache_read_tokens"] += cache_read

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "by_model": self.by_model,
        }


class BackstopCounter:
    """Counts deterministic backstop fires per run (WP16 §2.3).

    A backstop fires only when it actually repairs LLM output, so the count is the evidence
    for "does the current model still need the steering rule behind it?" — the number the
    steering ledger and ``eval.ablate`` read."""

    def __init__(self) -> None:
        self.fires: dict[str, int] = {}

    def record(self, event: TraceEvent) -> None:
        if event.kind != "backstop":
            return
        key = event.backstop_id or "unknown"
        self.fires[key] = self.fires.get(key, 0) + 1


def fanout(*recorders: Callable[[TraceEvent], None]) -> Callable[[TraceEvent], None]:
    """One trace recorder feeding several sinks (the writer *and* the backstop counter)."""

    def record(event: TraceEvent) -> None:
        for recorder in recorders:
            recorder(event)

    return record


def model_shape(model: DVModel) -> dict[str, Any]:
    """WHICH constructs a run built, not only how many (WP30.1).

    The result JSON carried `len(...)` and nothing else, `write_step_vault` wrote the model to a
    temp workdir the run then deletes, and the traces hold the re-model loop's DISCARDED
    attempts — reconstructing arm A from them gave 84 links where the run reported 51. So the
    arm comparison's open question (why does arm B build 73% of arm A's links?) could not be
    asked of anything on disk. This is what makes it askable, and it costs one dict per run.

    Links carry their GRAIN — the sorted hubs they connect — because that is the structural
    identity WP14 established: two runs may name the same relationship differently, and a
    name-keyed comparison would report that as a difference. Sorted for the same reason.

    Deliberately not the whole model: no descriptions, no requirement traces, no payloads. This
    exists to answer "which relationships exist and what do they span", and a fuller dump would
    grow every result file for questions nobody has asked."""
    def _link(lk: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "name": lk.name,
            "hubs": sorted(ref.hub for ref in lk.hub_refs),
        }
        # WP34: the staging ALIAS, recorded only where one exists so every pre-WP34 link
        # entry stays byte-identical. It is what makes §6's safety clause auditable from the
        # result file — "does the relation this link reads actually declare that column?" —
        # instead of requiring a reviewer to re-run the generator to find out.
        aliases = {
            ref.hub: ref.source_key_column
            for ref in lk.hub_refs
            if ref.source_key_column is not None
        }
        if aliases:
            entry["aliases"] = dict(sorted(aliases.items()))
        return entry

    return {
        "hubs": sorted(h.name for h in model.hubs),
        # WP34 (2026-08-12): BESIDE the hub list, never inside it — `hub_origin` and
        # `zero_satellite_hubs` index `hubs` as strings, and the archived runs cannot be
        # re-emitted in a richer form (pinned by tests/test_eval_result_additivity.py).
        #
        # The canonical key column is what the link proposer matches a foreign key against, so
        # without it "no existing hub is keyed on ProductID" is unfalsifiable from the result:
        # the 2026-08-12 run left 10 of 11 viable cross-schema foreign keys unexplained and
        # the leading hypothesis — hubs keyed off the referenced column — could not be checked
        # against anything on disk. Through the helper, because re-deriving it is the defect
        # class that once staged a hash from the wrong relation.
        "hub_keys": {h.name: canonical_hub_key_column(h) for h in sorted(
            model.hubs, key=lambda h: h.name
        )},
        "links": sorted(
            (_link(lk) for lk in model.links),
            key=lambda entry: str(entry["name"]),
        ),
        "satellites": sorted(
            ({"name": s.name, "parent": s.parent} for s in model.satellites),
            key=lambda entry: str(entry["name"]),
        ),
    }


def run_metrics(
    state: VaultAgentState,
    wall_clock_seconds: float,
    usage: UsageTotals,
    trace_path: Path | None = None,
    backstops: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Non-score observations captured per run (WP13 §3): cost, wall-clock, review-queue size.

    ``review_queue_lines`` is the *rendered* markdown line count — the readability proxy the
    scale test watches: does WP-aggregation keep the checkpoint scannable at hundreds of flags?
    ``trace_path`` (WP15) points at the run's LLM transcript, so a finding can cite the call
    that produced it instead of a hunch."""
    queue = assemble_review_queue(state)
    rendered = render_review_queue_md(queue)
    metrics: dict[str, Any] = {
        "wall_clock_seconds": round(wall_clock_seconds, 3),
        "usage": usage.as_dict(),
        "review_items_total": len(queue.items),
        "review_queue_lines": rendered.count("\n") + 1,
        "constructs": {
            "hubs": len(state.dv_model.hubs),
            "links": len(state.dv_model.links),
            "satellites": len(state.dv_model.satellites),
        },
        # WP30.1: the counts above say how big the answer is; this says what it is.
        "model": model_shape(state.dv_model),
        "flags": len(state.flags),
        # WP34 (2026-08-12): the breakdown, under a NEW key because `flags` is an integer in
        # every archived file and an int cannot be compared against a dict. Keyed by
        # `FlagKind`, which is what consumers branch on; the message text is never counted.
        "flag_kinds": dict(sorted(Counter(f.kind for f in state.flags).items())),
        # WP34 (2026-08-12): the link proposer's own bookkeeping. The 2026-08-12 run built 2
        # cross-domain links where 16 declared foreign keys crossed a schema and 11 had their
        # target hub already in the vault — and nothing in the result said whether the other
        # nine were never proposed, proposed and declined, or proposed and deduplicated. These
        # three counters separate exactly those cases; `{}` on greenfield runs, where the
        # proposer does not run at all.
        "link_proposals": {
            "by_category": dict(
                sorted(Counter(p.category for p in state.link_proposals.proposals).items())
            ),
            "by_status": dict(
                sorted(
                    Counter(
                        p.ratification_status for p in state.link_proposals.proposals
                    ).items()
                )
            ),
            "skipped": dict(
                sorted(Counter(s.reason for s in state.link_proposals.skipped).items())
            ),
        },
        # WP34: which validator codes fired, not merely whether the gate passed. §6's fourth
        # clause is "zero wrong joins", and E_LINK_KEY_NOT_IN_SOURCE is the gate that answers
        # it — a pass/fail boolean cannot distinguish "no link aliased anything" from "every
        # alias was sound". Counted by code because consumers must branch on the code, never
        # on the message.
        "validation_codes": dict(
            sorted(Counter(i.code for i in state.validation_report.issues if i.code).items())
        ),
        # WP16: {} means every backstop stayed idle this run — a rule with a persistently
        # empty count is the ablation runner's first candidate-delete.
        "backstop_fires": dict(sorted((backstops or {}).items())),
    }
    if trace_path is not None:
        metrics["trace_path"] = str(trace_path)
    return metrics


def chain_metrics(
    chain: list[tuple[EvalCase, VaultAgentState]],
    wall_clock_seconds: float,
    usage: UsageTotals,
    trace_path: Path | None = None,
    backstops: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Metrics for a chained run (WP30 §2.7), aggregated the way the ARM COMPARISON needs.

    Review load is the **sum** across steps, not the final step's: a human reviews every
    increment, so five checkpoints of 40 items each is 200 items of work, not 40. Reporting
    the last step alone would flatter the incremental arm precisely on the axis the WP30
    hypothesis is about. Construct counts and flags come from the final state, which is the
    vault that actually exists at the end; per-step review load is kept alongside so a
    growing or shrinking per-increment burden is visible rather than averaged away."""
    per_step = [
        {
            "case": step_case.name,
            "review_items": len(assemble_review_queue(state).items),
            "review_queue_lines": render_review_queue_md(assemble_review_queue(state)).count(
                "\n"
            )
            + 1,
            "constructs": {
                "hubs": len(state.dv_model.hubs),
                "links": len(state.dv_model.links),
                "satellites": len(state.dv_model.satellites),
            },
            # Per step as well as at the end: WHEN a link first appears is the arm comparison's
            # actual question — a relationship spanning two domains can only be built once the
            # second one has arrived, and only per-step shapes can show that.
            "model": model_shape(state.dv_model),
        }
        for step_case, state in chain
    ]
    metrics = run_metrics(chain[-1][1], wall_clock_seconds, usage, trace_path, backstops)
    metrics["review_items_total"] = sum(step["review_items"] for step in per_step)
    metrics["review_queue_lines"] = sum(
        step["review_queue_lines"] for step in per_step
    )
    metrics["chain_steps"] = per_step
    return metrics


async def run_case_once(case: EvalCase) -> VaultAgentState:
    """One real pipeline run for ``case``; auto-resumes the HITL checkpoint.

    Feeds the declared source schema (ADR-0004 grounding) and profiling (WP9 mapper) when the
    case carries them — the WP13 scale cases always do."""
    source_schemas = load_source_schemas(case.source_schema) if case.source_schema else []
    profiling = load_profiling(case.profiling) if case.profiling else {}
    # WP23: an extension case runs brownfield mode — the same input the CLI's --existing
    # provides. None for every greenfield case, which is all the pre-WP23 ones.
    existing = load_existing_model(case.existing) if case.existing else None
    saver = MemorySaver()
    # Same state-model allow-list the CLI registers on its sqlite saver: without it every
    # HITL resume deserialises our pydantic models as "unregistered types" (deprecation
    # warnings today, hard errors once langgraph enforces strict msgpack).
    saver.serde = _checkpoint_serde()
    compiled = build_graph().compile(checkpointer=saver)
    config: RunnableConfig = {"configurable": {"thread_id": uuid4().hex}}
    result = await compiled.ainvoke(
        # Same pragma as cli._run_pipeline: ainvoke's generic stub does not infer our
        # pydantic state as StateT; passing VaultAgentState is correct at runtime.
        VaultAgentState(  # type: ignore[arg-type]
            input_documents=[str(case.input_document)],
            source_schemas=source_schemas,
            profiling=profiling,
            existing_model=existing,
            existing_source=str(case.existing) if case.existing else None,
        ),
        config=config,
    )
    # A run can now pause more than once: WP29's resolution checkpoint stops before modelling
    # and hands the run on to the sign-off checkpoint. Answering only the first would leave
    # the run parked at the second and the harness would score a half-finished state as if it
    # were the outcome. Bounded, because an unanswerable interrupt must not spin forever.
    resumes = 0
    while "__interrupt__" in result:
        if resumes >= _MAX_AUTO_RESUMES:
            raise RuntimeError(
                f"the run was still paused after {_MAX_AUTO_RESUMES} automatic resumes; the "
                f"harness cannot answer this checkpoint"
            )
        result = await compiled.ainvoke(Command(resume=AUTO_RESUME_DECISION), config=config)
        resumes += 1
    data = {key: value for key, value in result.items() if key != "__interrupt__"}
    return VaultAgentState.model_validate(data)


def aggregate(runs: list[list[ScorerResult]]) -> dict[str, ScoreStats]:
    """Aggregate per-run scorer results into mean/min/max per scorer (pure)."""
    by_name: dict[str, list[float]] = {}
    for run in runs:
        for result in run:
            by_name.setdefault(result.name, []).append(result.score)
    return {
        name: ScoreStats(mean=sum(scores) / len(scores), min=min(scores), max=max(scores))
        for name, scores in by_name.items()
    }


def failed_gates(stats: dict[str, ScoreStats], case: EvalCase) -> list[str]:
    """Scorer names whose *mean* fell below the case's ``expectations.min_scores`` (pure)."""
    return [
        name
        for name, minimum in sorted(case.expectations.min_scores.items())
        if name in stats and stats[name].mean < minimum
    ]


def unsatisfiable_gates(
    stats: dict[str, ScoreStats], case: EvalCase, vacuous: Iterable[str] = ()
) -> list[str]:
    """Gates that cannot mean what the case author intends — *batch defects*, not scores (pure).

    Two ways a gate silently passes on absence of evidence, both real (WP18 §2.1/§2.3):

    1. **No score at all.** ``failed_gates`` only compares gates it finds in ``stats``, so a
       typo'd scorer name — or a case whose ``golden_mapping.yml`` is missing, which makes
       ``_score_run`` skip the whole mapping family — disables the gate without a word.
    2. **Vacuous in every repeat.** ``load_eval_case`` rejects this cheaply for the model
       scorers, but it cannot see the golden *mapping* (a separate file it never opens); the
       runner can, after scoring.

    Returns one rendered reason per offending gate, sorted. Deliberately separate from
    :func:`failed_gates`: a defective batch must never be reported as a failed score."""
    gated = set(case.expectations.min_scores)
    missing = [
        f"{name} is gated but produced no score (typo'd scorer name, or the case's "
        f"golden mapping is missing)"
        for name in sorted(gated - set(stats))
    ]
    empty = [
        f"{name} is gated but vacuous on this case (the golden declares nothing for it)"
        for name in sorted(gated & set(vacuous))
    ]
    return missing + empty


def build_result_payload(
    case: EvalCase,
    run_index: int,
    results: list[ScorerResult],
    *,
    models: dict[str, str],
    git_sha: str,
    timestamp: str,
    metrics: dict[str, Any] | None = None,
    mappings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The JSON document written for one run: scores, model ids, git SHA, diff details,
    (WP13) usage/wall-clock/review-queue metrics, and (WP14) the mapper's proposal dump.

    ``mappings`` is ``state.mappings.model_dump()`` — proposals + gaps + unresolved. It is
    added only when supplied, so callers that omit it (the payload-shape unit test) keep the
    pre-WP14 document; every live run passes it, so real result JSONs always carry it and one
    scale re-run can be inspected concept-by-concept."""
    payload: dict[str, Any] = {
        "case": case.name,
        "run": run_index,
        "timestamp": timestamp,
        "git_sha": git_sha,
        "models": models,
        "scores": {result.name: result.score for result in results},
        "details": {result.name: result.details for result in results},
        "metrics": metrics or {},
    }
    if mappings is not None:
        payload["mappings"] = mappings
    return payload


def render_table(
    case_name: str,
    stats: dict[str, ScoreStats],
    repeat: int,
    vacuous: Iterable[str] = (),
) -> str:
    """Compact per-case report: mean ± min/max per scorer across the repeats (pure).

    ``vacuous`` names scorers that had nothing to check on this case; they are marked
    inline, because a bare ``mean=1.000`` in the summary reads as a perfect score when it
    actually means "no golden to compare against" (the scale cases ship no golden model)."""
    lines = [f"{case_name} ({repeat} run(s)):"]
    width = max(len(name) for name in stats) if stats else 0
    marked = set(vacuous)
    lines.extend(
        f"  {name:<{width}}  mean={stat.mean:.3f}  min={stat.min:.3f}  max={stat.max:.3f}"
        + ("   (vacuous — nothing to check)" if name in marked else "")
        for name, stat in sorted(stats.items())
    )
    return "\n".join(lines)


def vacuous_scorers(runs: list[list[ScorerResult]]) -> list[str]:
    """Scorer names whose every run reported a vacuous verdict (pure).

    Keyed on the ``details`` prefix the scorers emit, which is theirs to define — the
    alternative, re-deriving vacuity from the case here, would duplicate that knowledge."""
    by_name: dict[str, list[bool]] = {}
    for run in runs:
        for result in run:
            by_name.setdefault(result.name, []).append(result.details.startswith("vacuous"))
    return sorted(name for name, flags in by_name.items() if flags and all(flags))


def render_metrics(case_name: str, metrics: list[dict[str, Any]]) -> str:
    """Compact per-case usage/wall-clock/review-queue summary across the repeats (pure)."""
    if not metrics:
        return f"  {case_name}: no metrics"
    n = len(metrics)
    wall = sum(m["wall_clock_seconds"] for m in metrics) / n
    tin = sum(m["usage"]["input_tokens"] for m in metrics) / n
    tout = sum(m["usage"]["output_tokens"] for m in metrics) / n
    cache = sum(m["usage"]["cache_read_tokens"] for m in metrics) / n
    calls = sum(m["usage"]["calls"] for m in metrics) / n
    review = sum(m["review_items_total"] for m in metrics) / n
    lines = sum(m["review_queue_lines"] for m in metrics) / n
    cache_share = cache / tin if tin else 0.0
    return (
        f"  usage (mean/run): {calls:.0f} calls, in={tin:,.0f} tok "
        f"(cache-read {cache_share:.0%}), out={tout:,.0f} tok · wall={wall:.1f}s · "
        f"review items={review:.0f} ({lines:.0f} rendered lines)"
    )


def _git_sha() -> str:
    try:
        return subprocess.run(  # fixed argv, repo introspection only
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _load_cases(args: argparse.Namespace) -> list[EvalCase]:
    if args.all:
        return load_all_cases()
    return [load_eval_case(DATASETS_ROOT / args.dataset / DATASET_FILENAME)]


def write_step_vault(state: VaultAgentState, step_dir: Path) -> Path:
    """Serialise a chain step's model exactly as ``cli.write_outputs`` does (WP30 §2.7).

    Deliberately the same bytes and the same location the CLI produces, so the next step
    consumes the real WP23 artifact through ``load_existing_model`` rather than a shortcut
    that could diverge from what a user's ``--existing`` would actually see."""
    meta_dir = step_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / DV_MODEL_FILENAME
    path.write_text(
        yaml.safe_dump(state.dv_model.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    return path


async def run_chain_once(
    case: EvalCase,
    workdir: Path,
    on_step: "Callable[[int, EvalCase, VaultAgentState], None] | None" = None,
) -> list[tuple[EvalCase, VaultAgentState]]:
    """Run every step of a chained case, threading each step's output into the next.

    Returns one ``(step_case, state)`` pair per step. A failing step raises, which
    ``_run_score_write`` turns into the usual WP14.1 partial-batch failure.

    ``on_step`` is called after each step completes, so the caller can persist that step
    BEFORE the next one is paid for. Without it, WP14.1's guarantee only holds per *repeat*:
    a five-step chain dying in step 5 would discard four completed, paid-for steps — the very
    loss WP14.1 exists to prevent, one level down. A failing ``on_step`` must never take the
    chain down (it is bookkeeping, not the measurement), so it is called defensively.

    Mid-chain human-in-the-loop semantics: every step auto-resumes with the standard
    unattended decision, exactly as a single-case run does. So a chain measures the pipeline
    WITHOUT human ratification quality — unratified mappings carry forward into the next
    step's inventory. That is conservative for the WP30 hypothesis rather than flattering to
    it, and the writeup must say so."""
    assert case.chain is not None
    runs: list[tuple[EvalCase, VaultAgentState]] = []
    previous: Path | None = None

    for index, step_name in enumerate(case.chain.steps, start=1):
        step_case = load_eval_case(DATASETS_ROOT / step_name / DATASET_FILENAME)
        if previous is not None:
            step_case = step_case.model_copy(update={"existing": previous})
        print(f"    step {index}/{len(case.chain.steps)}: {step_name} ...", flush=True)
        state = await run_case_once(step_case)
        runs.append((step_case, state))
        if on_step is not None:
            try:
                on_step(index, step_case, state)
            except Exception as exc:  # bookkeeping must never fail the measurement
                print(f"    (step {index} not persisted: {exc})", file=sys.stderr, flush=True)
        previous = write_step_vault(state, workdir / f"step{index}_{step_name}")

    return runs


def score_chain(
    case: EvalCase, runs: list[tuple[EvalCase, VaultAgentState]], golden_path: Path | None
) -> list[ScorerResult]:
    """Score a chain: the general scorers on the FINAL state, preservation PER STEP.

    Preservation aggregates as the **minimum** across the extending steps, never the mean:
    it is a promise, and a promise that held four times out of five was broken. The details
    name every step so a failure is attributable without re-running."""
    results = _score_run(case, runs[-1][1], golden_path)

    per_step = [
        (step_case.name, existing_construct_preservation(state, step_case))
        for step_case, state in runs[1:]  # step 1 is greenfield — nothing to preserve yet
    ]
    if per_step:
        worst_name, worst = min(per_step, key=lambda item: item[1].score)
        detail = "; ".join(f"{name}: {result.score:.3f}" for name, result in per_step)
        results = [r for r in results if r.name != worst.name]
        results.append(
            ScorerResult(
                name=worst.name,
                score=worst.score,
                details=(
                    f"min over {len(per_step)} extending step(s), worst {worst_name} — "
                    f"{detail}"
                ),
            )
        )
    return results


def _score_run(
    case: EvalCase, state: VaultAgentState, golden_path: Path | None
) -> list[ScorerResult]:
    """Construct scorers, plus the WP9 mapping scorers when the case has a golden mapping.

    The mapping scorers honour the case's ``mapping_match`` mode (WP14): ``column`` for the
    scale cases (pair-based coverage), ``concept`` for the name-aligned goldens."""
    results = score_state(state, case)
    if golden_path is not None and golden_path.is_file():
        results.extend(
            score_mapping(
                state.mappings, load_golden_mapping(golden_path), mode=case.mapping_match
            )
        )
    results.extend(_score_resolution(case, state))
    return results


def _score_resolution(case: EvalCase, state: VaultAgentState) -> list[ScorerResult]:
    """The resolution scorer family, dispatched by the ``golden_resolution.yml`` convention.

    Deliberately NOT silent when the golden is absent-but-gated. ``_score_run`` skipping the
    mapping family for a missing ``golden_mapping.yml`` is the exact hole WP18 §2.1 had to
    paper over afterwards (``unsatisfiable_gates``, "no score at all"), and this would have
    reproduced it: a case gating ``false_merge_rate`` whose golden went missing would produce
    no such score, and a gate that is never computed is a gate that never fails. Here the
    family is simply not dispatched, and WP18's machinery then reports the gate as
    unsatisfiable — a batch defect, which is what it is, rather than a pass.

    A case that HAS the golden and produced no resolutions scores through the scorers' own
    vacuity convention, loudly, rather than being skipped here."""
    if case.input_document is None:
        return []
    golden_file = case.input_document.parent / GOLDEN_RESOLUTION_FILENAME
    if not golden_file.is_file():
        return []
    golden = load_golden_resolution(golden_file)
    return [
        false_merge_rate(golden, state.resolutions),
        resolution_accuracy(golden, state.resolutions),
        new_hub_detection(golden, state.resolutions),
        resolution_calibration(golden, state.resolutions),
    ]


async def _run_score_write(
    case: EvalCase,
    golden_path: Path | None,
    repeat: int,
    *,
    out_root: Path,
    models: dict[str, str],
    git_sha: str,
) -> tuple[list[list[ScorerResult]], list[dict[str, Any]], list[Path], tuple[int, str] | None]:
    """Run + score + **persist each repeat immediately** (WP14.1, findings Candidate #3).

    A repeat's JSON (scores + metrics + proposal dump) is written the moment that repeat is
    scored, not after the whole batch — so a mid-batch failure (e.g. an exhausted credit
    balance: a non-retryable 4xx the ForcedToolCaller correctly does not retry) never discards
    a completed, paid-for run again. On such a failure the loop stops and returns
    ``(failed_repeat_index, reason)``; the caller renders the partial summary and exits
    non-zero. Only ``run_case_once`` (the LLM batch) is guarded — the deterministic
    score/metrics/write step is not expected to fail on a completed run.

    Returns the completed repeats' scorer results + metrics, the written paths, and the
    failure marker (``None`` on a fully green batch). The usage recorder is a module-level
    ForcedToolCaller hook, installed per run and always cleared."""
    runs: list[list[ScorerResult]] = []
    metrics: list[dict[str, Any]] = []
    written: list[Path] = []
    for index in range(repeat):
        print(f"  run {index + 1}/{repeat} ...", flush=True)
        usage = UsageTotals()
        # The result JSON's timestamp is stamped *before* the run so the trace written during
        # it can share the filename stem — result and transcript sit side by side (WP15 §2.4).
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        trace_path = out_root / case.name / f"{timestamp}-run{index + 1}.trace.jsonl"
        backstops = BackstopCounter()
        llm.set_usage_recorder(usage.record)
        llm.set_trace_recorder(fanout(JsonlTraceWriter(trace_path), backstops.record))
        started = time.perf_counter()
        chain: list[tuple[EvalCase, VaultAgentState]] = []
        try:
            if case.chain is not None:
                # One temp workdir per repeat: each step writes its metadata/dv_model.yml
                # there and the next step reads it, so the chain runs the real WP23 path.
                def persist_step(
                    step_index: int,
                    step_case: EvalCase,
                    step_state: VaultAgentState,
                    *,
                    repeat_index: int = index + 1,
                    repeat_usage: UsageTotals = usage,
                    repeat_trace: Path = trace_path,
                    repeat_stamp: str = timestamp,
                ) -> None:
                    """WP14.1 semantics one level down: a step is on disk before the next one
                    is paid for, so a chain dying at step 5 leaves four measurements, not
                    nothing. Scored against the STEP's own golden — each subject area ships
                    one — so the partial data is usable, not just a state dump."""
                    step_golden = DATASETS_ROOT / step_case.name / GOLDEN_MAPPING_FILENAME
                    _write_one_result(
                        case, repeat_index,
                        _score_run(
                            step_case, step_state,
                            step_golden if step_golden.is_file() else None,
                        ),
                        out_root, models, git_sha,
                        metrics=run_metrics(step_state, 0.0, repeat_usage, repeat_trace, {}),
                        mappings=step_state.mappings.model_dump(mode="json"),
                        timestamp=f"{repeat_stamp}-step{step_index}-{step_case.name}",
                    )

                with tempfile.TemporaryDirectory() as workdir:
                    chain = await run_chain_once(case, Path(workdir), on_step=persist_step)
                state = chain[-1][1]
            else:
                state = await run_case_once(case)
        except Exception as exc:  # any run failure: flush the completed repeats, don't lose them
            return runs, metrics, written, (index + 1, f"{type(exc).__name__}: {exc}")
        finally:
            llm.set_usage_recorder(None)
            llm.set_trace_recorder(None)
        elapsed = time.perf_counter() - started
        if chain:
            results = score_chain(case, chain, golden_path)
            run_meta = chain_metrics(chain, elapsed, usage, trace_path, backstops.fires)
        else:
            results = _score_run(case, state, golden_path)
            run_meta = run_metrics(state, elapsed, usage, trace_path, backstops.fires)
        mapping_dump = state.mappings.model_dump(mode="json")
        written.append(
            _write_one_result(
                case, index + 1, results, out_root, models, git_sha, run_meta, mapping_dump,
                timestamp,
            )
        )
        runs.append(results)
        metrics.append(run_meta)
    return runs, metrics, written, None


def _write_one_result(
    case: EvalCase,
    run_index: int,
    results: list[ScorerResult],
    out_root: Path,
    models: dict[str, str],
    git_sha: str,
    metrics: dict[str, Any],
    mappings: dict[str, Any],
    timestamp: str | None = None,
) -> Path:
    """Persist one repeat's result JSON immediately (WP14.1). Same filename scheme and payload
    as before — one timestamped JSON per repeat — only written sooner (inside the loop).

    ``timestamp`` is stamped by the caller (WP15: shared with the run's trace file); omitted,
    it is taken now, keeping the pre-WP15 behaviour for any other caller."""
    case_dir = out_root / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    payload = build_result_payload(
        case, run_index, results, models=models, git_sha=git_sha,
        timestamp=timestamp, metrics=metrics, mappings=mappings,
    )
    path = case_dir / f"{timestamp}-run{run_index}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.run", description="Run the live eval harness (real LLM calls)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dataset", help="name of one case under eval/datasets/")
    group.add_argument("--all", action="store_true", help="run every shipped case")
    parser.add_argument(
        "--repeat", type=int, default=DEFAULT_REPEAT, help="runs per case (exposes variance)"
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="directory for per-run JSON results"
    )
    args = parser.parse_args(argv)

    # The project convention keeps the key in .env (config.Settings reads it via
    # pydantic-settings); load it here too so `python -m eval.run` works from a checkout
    # without exporting the variable manually.
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "eval.run needs real LLM calls: set ANTHROPIC_API_KEY (the deterministic "
            "scorers are unit-tested keylessly; this runner is never part of pytest).",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    models = {"primary_model": settings.primary_model, "heavy_model": settings.heavy_model}
    git_sha = _git_sha()

    # Optional LangSmith layer (spec §6): silently disabled without the key/package.
    from eval.langsmith_upload import make_client, upload_run_results

    langsmith_client = make_client(settings)

    exit_code = 0
    for case in _load_cases(args):
        print(f"Evaluating case '{case.name}' ...", flush=True)
        # A WP13 generate case synthesises its inputs into a temp workdir on demand; a
        # committed case is returned unchanged with its shipped golden-mapping path.
        with tempfile.TemporaryDirectory(prefix=f"eval-{case.name}-") as workdir:
            resolved, golden_path = materialize_case(case, Path(workdir))
            if resolved.generate is not None:
                print(
                    f"  generated landscape: {resolved.generate.tables} tables "
                    f"(seed {resolved.generate.seed})",
                    flush=True,
                )
            runs, metrics, written, failure = asyncio.run(
                _run_score_write(
                    resolved, golden_path, args.repeat,
                    out_root=args.out, models=models, git_sha=git_sha,
                )
            )
        # Each completed repeat is already on disk (WP14.1); the summary renders from the
        # in-memory results of whatever completed — the full batch on success, the partial
        # set when a mid-batch failure cut it short.
        stats = aggregate(runs)
        vacuous = vacuous_scorers(runs)
        print(render_table(case.name, stats, len(runs), vacuous))
        print(render_metrics(case.name, metrics))
        if written:
            print(f"  results: {', '.join(str(path) for path in written)}")
        if failure is not None:
            failed_repeat, reason = failure
            print(
                f"  BATCH INCOMPLETE: run {failed_repeat}/{args.repeat} failed and was not "
                f"persisted ({reason}); {len(runs)}/{args.repeat} run(s) completed and saved",
                file=sys.stderr,
            )
            exit_code = 1
        if langsmith_client is not None and runs:
            upload_run_results(langsmith_client, case, runs, models=models, git_sha=git_sha)
            print(f"  uploaded to LangSmith ('{settings.langsmith_project}' workspace)")
        # A gate that could not be evaluated is a defect in the batch, reported before any
        # score verdict. Skipped when nothing completed at all: with zero repeats every gate
        # is trivially unscored, and the BATCH INCOMPLETE line above already says why.
        if runs:
            for reason in unsatisfiable_gates(stats, case, vacuous):
                print(f"  GATE UNSATISFIABLE: {reason}", file=sys.stderr)
                exit_code = 1
        for name in failed_gates(stats, case):
            print(
                f"  GATE FAILED: {name} mean {stats[name].mean:.3f} < "
                f"min_scores[{name}]={case.expectations.min_scores[name]}",
                file=sys.stderr,
            )
            exit_code = 1
        if failure is not None:
            # A run failure (e.g. an exhausted credit balance) is fatal and stays fatal — do
            # not burn money re-attempting the remaining cases in an --all batch.
            break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
