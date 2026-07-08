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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from eval.datasets import DATASET_FILENAME, DATASETS_ROOT, EvalCase, load_all_cases, load_eval_case
from eval.scorers import ScorerResult, score_state
from vault_agent.config import get_settings
from vault_agent.graph import build_graph
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


async def run_case_once(case: EvalCase) -> VaultAgentState:
    """One real pipeline run for ``case``; auto-resumes the HITL checkpoint."""
    source_schemas = load_source_schemas(case.source_schema) if case.source_schema else []
    compiled = build_graph().compile(checkpointer=MemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": uuid4().hex}}
    result = await compiled.ainvoke(
        # Same pragma as cli._run_pipeline: ainvoke's generic stub does not infer our
        # pydantic state as StateT; passing VaultAgentState is correct at runtime.
        VaultAgentState(  # type: ignore[arg-type]
            input_documents=[str(case.input_document)],
            source_schemas=source_schemas,
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
) -> dict[str, Any]:
    """The JSON document written for one run: scores, model ids, git SHA, diff details."""
    return {
        "case": case.name,
        "run": run_index,
        "timestamp": timestamp,
        "git_sha": git_sha,
        "models": models,
        "scores": {result.name: result.score for result in results},
        "details": {result.name: result.details for result in results},
    }


def render_table(case_name: str, stats: dict[str, ScoreStats], repeat: int) -> str:
    """Compact per-case report: mean ± min/max per scorer across the repeats (pure)."""
    lines = [f"{case_name} ({repeat} run(s)):"]
    width = max(len(name) for name in stats) if stats else 0
    lines.extend(
        f"  {name:<{width}}  mean={stat.mean:.3f}  min={stat.min:.3f}  max={stat.max:.3f}"
        for name, stat in sorted(stats.items())
    )
    return "\n".join(lines)


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


async def _run_and_score(case: EvalCase, repeat: int) -> list[list[ScorerResult]]:
    runs: list[list[ScorerResult]] = []
    for index in range(repeat):
        print(f"  run {index + 1}/{repeat} ...", flush=True)
        state = await run_case_once(case)
        runs.append(score_state(state, case))
    return runs


def _write_results(
    case: EvalCase,
    runs: list[list[ScorerResult]],
    out_root: Path,
    models: dict[str, str],
    git_sha: str,
) -> list[Path]:
    case_dir = out_root / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, results in enumerate(runs, start=1):
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        payload = build_result_payload(
            case, index, results, models=models, git_sha=git_sha, timestamp=timestamp
        )
        path = case_dir / f"{timestamp}-run{index}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        written.append(path)
    return written


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
        runs = asyncio.run(_run_and_score(case, args.repeat))
        stats = aggregate(runs)
        written = _write_results(case, runs, args.out, models, git_sha)
        print(render_table(case.name, stats, args.repeat))
        print(f"  results: {', '.join(str(path) for path in written)}")
        if langsmith_client is not None:
            upload_run_results(langsmith_client, case, runs, models=models, git_sha=git_sha)
            print(f"  uploaded to LangSmith ('{settings.langsmith_project}' workspace)")
        for name in failed_gates(stats, case):
            print(
                f"  GATE FAILED: {name} mean {stats[name].mean:.3f} < "
                f"min_scores[{name}]={case.expectations.min_scores[name]}",
                file=sys.stderr,
            )
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
