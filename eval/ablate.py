"""Steering-rule ablation runner (WP16 §2.4) — the measuring instrument, not a verdict.

Answers one question per invocation: *does the current model still need this steering rule?*
It runs a golden case twice — **baseline** (the shipped prompt) and **dropped** (the same
prompt minus one named :class:`~vault_agent.rules.dv2_rules.SteeringRule`) — and records for
both arms the scores, the validation issue codes, the deterministic backstop fires, and the
token usage. A rule whose dropped arm shows *zero backstop fires and no gated-score
regression* across N >= 3 repeats becomes a ``candidate-delete`` in
``docs/architecture/steering-ledger.md``; a human decides — this runner never deletes
anything, and validator gates are never ablated (they are the product, not model-compensation).

Usage::

    uv run python -m eval.ablate --case health_insurance --drop cdk_not_payload --repeat 3
    uv run python -m eval.ablate --case bank --drop unit_of_work --model claude-sonnet-5

Real LLM calls, so it needs ``ANTHROPIC_API_KEY`` and is never part of pytest; the pure
helpers (summarising, rendering, persistence) are keyless and unit-tested. WP14.1 semantics
apply: the comparison JSON is rewritten after **every completed repeat**, so an exhausted
credit balance mid-run never discards a paid-for arm.
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.datasets import (
    DATASET_FILENAME,
    DATASETS_ROOT,
    EvalCase,
    load_eval_case,
    materialize_case,
)
from eval.run import (
    BackstopCounter,
    UsageTotals,
    _git_sha,
    _score_run,
    fanout,
    run_case_once,
)
from vault_agent import llm
from vault_agent.rules.dv2_rules import DV_MODELING_RULES, set_excluded_rules
from vault_agent.state import VaultAgentState
from vault_agent.trace import JsonlTraceWriter

DEFAULT_REPEAT = 3
DEFAULT_OUT = Path("eval") / "results" / "ablation"

BASELINE = "baseline"
DROPPED = "dropped"
ARMS = (BASELINE, DROPPED)


def rule_by_id(rule_id: str) -> Any:
    """The registry entry for ``rule_id`` (attributable error in the house loader style)."""
    for rule in DV_MODELING_RULES:
        if rule.id == rule_id:
            return rule
    known = ", ".join(sorted(rule.id for rule in DV_MODELING_RULES))
    raise ValueError(f"unknown steering rule id {rule_id!r}; known ids: {known}")


def issue_codes(state: VaultAgentState) -> dict[str, int]:
    """Validation issue codes and their counts (the "did dropping it break modelling?" signal)."""
    counts: dict[str, int] = {}
    for issue in state.validation_report.issues:
        key = issue.code or "issue"
        counts[key] = counts.get(key, 0) + 1
    return counts


def summarise_arm(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one arm's repeats: mean score per scorer, total backstop fires, totals (pure)."""
    scores: dict[str, list[float]] = {}
    fires: dict[str, int] = {}
    codes: dict[str, int] = {}
    for record in records:
        for name, score in record["scores"].items():
            scores.setdefault(name, []).append(score)
        for key, count in record["backstop_fires"].items():
            fires[key] = fires.get(key, 0) + count
        for code, count in record["validation_issue_codes"].items():
            codes[code] = codes.get(code, 0) + count
    return {
        "repeats": len(records),
        "mean_scores": {name: sum(v) / len(v) for name, v in sorted(scores.items())},
        "backstop_fires": dict(sorted(fires.items())),
        "validation_issue_codes": dict(sorted(codes.items())),
        "validation_passed": [record["validation_passed"] for record in records],
        "input_tokens": sum(record["usage"]["input_tokens"] for record in records),
        "output_tokens": sum(record["usage"]["output_tokens"] for record in records),
        "runs": records,
    }


def render_comparison(report: dict[str, Any]) -> str:
    """Two-column baseline-vs-dropped summary (pure)."""
    baseline = report["arms"].get(BASELINE, {})
    dropped = report["arms"].get(DROPPED, {})
    lines = [
        f"ablation: case '{report['case']}' × rule '{report['rule']}' "
        f"({report['repeats']} repeat(s) per arm)",
        f"  {'':<28}{BASELINE:>12}{DROPPED:>12}",
    ]
    names = sorted(set(baseline.get("mean_scores", {})) | set(dropped.get("mean_scores", {})))
    for name in names:
        left = baseline.get("mean_scores", {}).get(name)
        right = dropped.get("mean_scores", {}).get(name)
        lines.append(
            f"  {name:<28}{_num(left):>12}{_num(right):>12}"
        )
    totals = (("backstop fires", "backstop_fires"), ("validation issues", "validation_issue_codes"))
    for label, key in totals:
        left = sum(baseline.get(key, {}).values())
        right = sum(dropped.get(key, {}).values())
        lines.append(f"  {label:<28}{left:>12}{right:>12}")
    fires = dropped.get("backstop_fires", {})
    if fires:
        lines.append(
            f"  → the dropped arm needed its backstop(s): "
            f"{', '.join(f'{k}×{v}' for k, v in fires.items())} — rule still earns its place"
        )
    elif dropped:
        lines.append(
            "  → zero backstop fires in the dropped arm — candidate-delete IF the gated "
            "scores held; record the verdict in docs/architecture/steering-ledger.md"
        )
    return "\n".join(lines)


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


async def run_ablation(
    case: EvalCase,
    golden_path: Path | None,
    rule_id: str,
    *,
    repeat: int,
    out_path: Path,
    models: dict[str, str],
    git_sha: str,
    timestamp: str,
) -> tuple[dict[str, Any], tuple[str, int, str] | None]:
    """Run both arms and persist after every completed repeat (WP14.1 crash-safety).

    Returns ``(report, failure)`` where ``failure`` is ``(arm, repeat, reason)`` when a run
    raised — everything completed before it is already on disk and in the report."""
    report: dict[str, Any] = {
        "case": case.name,
        "rule": rule_id,
        "rule_text": rule_by_id(rule_id).text,
        "backstop": rule_by_id(rule_id).backstop,
        "repeats": repeat,
        "timestamp": timestamp,
        "git_sha": git_sha,
        "models": models,
        "arms": {},
    }
    _persist(report, out_path)
    for arm in ARMS:
        records: list[dict[str, Any]] = []
        # The exclusion is a module-level seam (never set by production code); always cleared,
        # including on a failure, so a crashed ablation cannot leave the prompt mutilated.
        set_excluded_rules([rule_id] if arm == DROPPED else None)
        try:
            for index in range(repeat):
                print(f"  {arm} run {index + 1}/{repeat} ...", flush=True)
                try:
                    record = await _one_run(case, golden_path, out_path, arm, index + 1)
                except Exception as exc:  # noqa: BLE001 - persist what completed, then stop
                    report["arms"][arm] = summarise_arm(records)
                    _persist(report, out_path)
                    return report, (arm, index + 1, f"{type(exc).__name__}: {exc}")
                records.append(record)
                report["arms"][arm] = summarise_arm(records)
                _persist(report, out_path)
        finally:
            set_excluded_rules(None)
    return report, None


async def _one_run(
    case: EvalCase, golden_path: Path | None, out_path: Path, arm: str, run_index: int
) -> dict[str, Any]:
    """One scored pipeline run with usage/backstop/trace capture registered around it."""
    usage = UsageTotals()
    backstops = BackstopCounter()
    trace_path = out_path.with_suffix("").with_name(
        f"{out_path.with_suffix('').name}-{arm}-run{run_index}.trace.jsonl"
    )
    llm.set_usage_recorder(usage.record)
    llm.set_trace_recorder(fanout(JsonlTraceWriter(trace_path), backstops.record))
    started = time.perf_counter()
    try:
        state = await run_case_once(case)
    finally:
        llm.set_usage_recorder(None)
        llm.set_trace_recorder(None)
    results = _score_run(case, state, golden_path)
    return {
        "run": run_index,
        "wall_clock_seconds": round(time.perf_counter() - started, 3),
        "scores": {result.name: result.score for result in results},
        "validation_passed": state.validation_report.passed,
        "validation_issue_codes": issue_codes(state),
        "backstop_fires": dict(sorted(backstops.fires.items())),
        "usage": usage.as_dict(),
        "trace_path": str(trace_path),
    }


def _persist(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.ablate",
        description="Measure whether a modeler steering rule is still needed (WP16).",
    )
    parser.add_argument("--case", required=True, help="name of one case under eval/datasets/")
    parser.add_argument("--drop", required=True, help="steering rule id to ablate")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help="runs per arm")
    parser.add_argument("--model", help="override the modeler tier (candidate-model probe)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="comparison JSON directory")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "eval.ablate needs real LLM calls: set ANTHROPIC_API_KEY (the registry, seam, "
            "and summary helpers are unit-tested keylessly).",
            file=sys.stderr,
        )
        return 2
    try:
        rule = rule_by_id(args.drop)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.model:
        # The modeler reads settings.heavy_model when it builds its caller; override through
        # the environment and drop the cached Settings so the next run picks it up.
        os.environ["HEAVY_MODEL"] = args.model
        from vault_agent.config import get_settings as _get_settings

        _get_settings.cache_clear()

    from vault_agent.config import get_settings

    settings = get_settings()
    models = {"primary_model": settings.primary_model, "heavy_model": settings.heavy_model}
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out_path = args.out / f"{args.case}-{args.drop}-{timestamp}.json"

    case = load_eval_case(DATASETS_ROOT / args.case / DATASET_FILENAME)
    print(f"Ablating '{rule.id}' on case '{case.name}' (backstop: {rule.backstop or 'none'})")
    with tempfile.TemporaryDirectory(prefix=f"ablate-{case.name}-") as workdir:
        resolved, golden_path = materialize_case(case, Path(workdir))
        report, failure = asyncio.run(
            run_ablation(
                resolved, golden_path, rule.id,
                repeat=args.repeat, out_path=out_path, models=models,
                git_sha=_git_sha(), timestamp=timestamp,
            )
        )
    print(render_comparison(report))
    print(f"  comparison: {out_path}")
    if failure is not None:
        arm, index, reason = failure
        print(
            f"  ABLATION INCOMPLETE: {arm} run {index}/{args.repeat} failed ({reason}); "
            f"everything completed before it is saved",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
