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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from eval.datasets import (
    DATASET_FILENAME,
    DATASETS_ROOT,
    EvalCase,
    load_all_cases,
    load_eval_case,
    materialize_case,
)
from eval.mapping import load_golden_mapping
from eval.scorers import ScorerResult, score_mapping, score_state
from vault_agent import llm
from vault_agent.agents.orchestrator import assemble_review_queue, render_review_queue_md
from vault_agent.cli import _checkpoint_serde
from vault_agent.config import get_settings
from vault_agent.graph import build_graph
from vault_agent.profiling import load_profiling
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import VaultAgentState

DEFAULT_REPEAT = 3
DEFAULT_OUT = Path("eval") / "results"

# The eval runs unattended: when the human-in-the-loop checkpoint interrupts (it usually
# does — generated contracts carry placeholder owners), resume exactly like
# ``vault-agent resume --accept`` with no owners assigned, so the run completes through
# the ADR author. Unassigned owners still show up as flags/review items and are scored.
AUTO_RESUME_DECISION: dict[str, Any] = {"owners": {}, "accept": True}


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


def run_metrics(
    state: VaultAgentState, wall_clock_seconds: float, usage: UsageTotals
) -> dict[str, Any]:
    """Non-score observations captured per run (WP13 §3): cost, wall-clock, review-queue size.

    ``review_queue_lines`` is the *rendered* markdown line count — the readability proxy the
    scale test watches: does WP-aggregation keep the checkpoint scannable at hundreds of flags?"""
    queue = assemble_review_queue(state)
    rendered = render_review_queue_md(queue)
    return {
        "wall_clock_seconds": round(wall_clock_seconds, 3),
        "usage": usage.as_dict(),
        "review_items_total": len(queue.items),
        "review_queue_lines": rendered.count("\n") + 1,
        "constructs": {
            "hubs": len(state.dv_model.hubs),
            "links": len(state.dv_model.links),
            "satellites": len(state.dv_model.satellites),
        },
        "flags": len(state.flags),
    }


async def run_case_once(case: EvalCase) -> VaultAgentState:
    """One real pipeline run for ``case``; auto-resumes the HITL checkpoint.

    Feeds the declared source schema (ADR-0004 grounding) and profiling (WP9 mapper) when the
    case carries them — the WP13 scale cases always do."""
    source_schemas = load_source_schemas(case.source_schema) if case.source_schema else []
    profiling = load_profiling(case.profiling) if case.profiling else {}
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
        ),
        config=config,
    )
    if "__interrupt__" in result:
        result = await compiled.ainvoke(Command(resume=AUTO_RESUME_DECISION), config=config)
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


def render_table(case_name: str, stats: dict[str, ScoreStats], repeat: int) -> str:
    """Compact per-case report: mean ± min/max per scorer across the repeats (pure)."""
    lines = [f"{case_name} ({repeat} run(s)):"]
    width = max(len(name) for name in stats) if stats else 0
    lines.extend(
        f"  {name:<{width}}  mean={stat.mean:.3f}  min={stat.min:.3f}  max={stat.max:.3f}"
        for name, stat in sorted(stats.items())
    )
    return "\n".join(lines)


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
    return results


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
        llm.set_usage_recorder(usage.record)
        started = time.perf_counter()
        try:
            state = await run_case_once(case)
        except Exception as exc:  # any run failure: flush the completed repeats, don't lose them
            return runs, metrics, written, (index + 1, f"{type(exc).__name__}: {exc}")
        finally:
            llm.set_usage_recorder(None)
        elapsed = time.perf_counter() - started
        results = _score_run(case, state, golden_path)
        run_meta = run_metrics(state, elapsed, usage)
        mapping_dump = state.mappings.model_dump(mode="json")
        written.append(
            _write_one_result(
                case, index + 1, results, out_root, models, git_sha, run_meta, mapping_dump
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
) -> Path:
    """Persist one repeat's result JSON immediately (WP14.1). Same filename scheme and payload
    as before — one timestamped JSON per repeat — only written sooner (inside the loop)."""
    case_dir = out_root / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
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
        print(render_table(case.name, stats, len(runs)))
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
