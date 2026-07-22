"""Keyless tests for the live runner's pure helpers (WP6 layer 3).

The runner itself needs an API key and is never executed here — these tests cover the
deterministic parts: aggregation, the min_scores gate, the JSON payload, the report
table, and the missing-key guard."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval import run as run_mod
from eval.datasets import EvalCase, Expectations, GoldenModel
from eval.mapping import ProposedMapping
from eval.run import (
    ScoreStats,
    aggregate,
    build_result_payload,
    failed_gates,
    main,
    render_table,
)
from eval.scorers import ScorerResult


def _result(name: str, score: float, details: str = "d") -> ScorerResult:
    return ScorerResult(name=name, score=score, details=details)


def _case(min_scores: dict[str, float] | None = None) -> EvalCase:
    return EvalCase(
        name="synthetic",
        input_document="unused.md",
        golden=GoldenModel(),
        expectations=Expectations(min_scores=min_scores or {}),
    )


def test_aggregate_mean_min_max_across_repeats() -> None:
    runs = [
        [_result("construct_f1", 0.5), _result("pipeline_health", 1.0)],
        [_result("construct_f1", 1.0), _result("pipeline_health", 1.0)],
    ]
    stats = aggregate(runs)
    assert stats["construct_f1"] == ScoreStats(mean=0.75, min=0.5, max=1.0)
    assert stats["pipeline_health"] == ScoreStats(mean=1.0, min=1.0, max=1.0)


def test_failed_gates_compares_means_against_min_scores() -> None:
    stats = {
        "construct_f1": ScoreStats(mean=0.75, min=0.5, max=1.0),
        "pipeline_health": ScoreStats(mean=1.0, min=1.0, max=1.0),
    }
    case = _case({"construct_f1": 0.8, "pipeline_health": 1.0, "not_a_scorer": 0.9})
    assert failed_gates(stats, case) == ["construct_f1"]
    assert failed_gates(stats, _case()) == []


def test_build_result_payload_shape() -> None:
    payload = build_result_payload(
        _case(),
        2,
        [_result("construct_f1", 0.5, "hubs: 1/2")],
        models={"primary_model": "claude-sonnet-4-6", "heavy_model": "claude-opus-4-8"},
        git_sha="abc1234",
        timestamp="20260708T000000000000Z",
    )
    assert payload == {
        "case": "synthetic",
        "run": 2,
        "timestamp": "20260708T000000000000Z",
        "git_sha": "abc1234",
        "models": {"primary_model": "claude-sonnet-4-6", "heavy_model": "claude-opus-4-8"},
        "scores": {"construct_f1": 0.5},
        "details": {"construct_f1": "hubs: 1/2"},
        "metrics": {},
    }


def test_build_result_payload_includes_mappings_when_given() -> None:
    # WP14: the mapper's proposal dump is written into every live result JSON, but only when
    # supplied — the shape test above (which omits it) stays byte-identical.
    dump = {
        "proposals": [{"concept": "x", "table": "T", "column": "C"}],
        "gaps": [],
        "unresolved": [],
    }
    payload = build_result_payload(
        _case(),
        1,
        [_result("mapping_coverage", 0.8)],
        models={"primary_model": "claude-sonnet-4-6", "heavy_model": "claude-opus-4-8"},
        git_sha="abc1234",
        timestamp="20260719T000000000000Z",
        mappings=dump,
    )
    assert payload["mappings"] == dump


def test_render_table_shows_mean_min_max_per_scorer() -> None:
    table = render_table(
        "bank",
        {"construct_f1": ScoreStats(mean=0.875, min=0.75, max=1.0)},
        repeat=2,
    )
    assert "bank (2 run(s)):" in table
    assert "construct_f1  mean=0.875  min=0.750  max=1.000" in table


def _stub_runner(monkeypatch: pytest.MonkeyPatch, scores: ScorerResult) -> None:
    """Stub the run/score/metrics seams so _run_score_write is keyless (no graph, no key).

    ``run_case_once`` returns a fake state exposing only ``.mappings`` (all the write loop
    reads off it); ``_score_run``/``run_metrics`` return fixed, JSON-serialisable payloads."""
    monkeypatch.setattr(run_mod, "_score_run", lambda case, state, golden: [scores])
    monkeypatch.setattr(
        run_mod, "run_metrics",
        lambda *args, **kwargs: {"wall_clock_seconds": 1.0}
    )


def test_run_score_write_persists_completed_repeats_before_a_mid_batch_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # WP14.1 (findings Candidate #3): a run-2 failure must leave run 1's paid-for JSON on disk.
    attempts = {"n": 0}

    async def fake_run_case_once(case: EvalCase) -> SimpleNamespace:
        attempts["n"] += 1
        if attempts["n"] == 2:
            raise RuntimeError("credit balance too low")  # non-retryable 4xx analog
        return SimpleNamespace(mappings=ProposedMapping())

    monkeypatch.setattr(run_mod, "run_case_once", fake_run_case_once)
    _stub_runner(monkeypatch, _result("mapping_coverage", 1.0))

    runs, metrics, written, failure = asyncio.run(
        run_mod._run_score_write(
            _case(), None, 3,
            out_root=tmp_path, models={"primary_model": "m", "heavy_model": "h"}, git_sha="abc",
        )
    )
    assert len(runs) == 1 and len(metrics) == 1
    assert len(written) == 1 and written[0].is_file()  # run 1 persisted despite the run-2 crash
    assert failure == (2, "RuntimeError: credit balance too low")
    payload = json.loads(written[0].read_text())
    assert payload["run"] == 1
    assert payload["scores"] == {"mapping_coverage": 1.0}
    assert payload["mappings"] == {"proposals": [], "gaps": [], "unresolved": []}


def test_run_score_write_success_persists_every_repeat(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_case_once(case: EvalCase) -> SimpleNamespace:
        return SimpleNamespace(mappings=ProposedMapping())

    monkeypatch.setattr(run_mod, "run_case_once", fake_run_case_once)
    _stub_runner(monkeypatch, _result("construct_f1", 0.5))

    runs, metrics, written, failure = asyncio.run(
        run_mod._run_score_write(
            _case(), None, 3,
            out_root=tmp_path, models={"primary_model": "m", "heavy_model": "h"}, git_sha="abc",
        )
    )
    assert failure is None
    assert len(runs) == 3 and len(written) == 3 and all(path.is_file() for path in written)
    assert {json.loads(path.read_text())["run"] for path in written} == {1, 2, 3}


def test_main_without_api_key_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # main() calls load_dotenv() for developer convenience, which would repopulate
    # ANTHROPIC_API_KEY from a real .env on a dev box and defeat this test. Neutralise it
    # so "no key" means no key regardless of whether a .env exists in the working dir.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--dataset", "bank"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


# --- WP15/WP16: trace path and backstop-fire metrics ---------------------------------------


def test_backstop_counter_counts_only_backstop_events() -> None:
    from vault_agent.llm import TraceEvent

    counter = run_mod.BackstopCounter()
    counter.record(TraceEvent(kind="llm_call", tool_name="emit_dv_model"))
    counter.record(TraceEvent(kind="backstop", backstop_id="attributes_without_cdk"))
    counter.record(TraceEvent(kind="backstop", backstop_id="attributes_without_cdk"))
    counter.record(TraceEvent(kind="backstop", backstop_id="fk_demotion"))

    assert counter.fires == {"attributes_without_cdk": 2, "fk_demotion": 1}


def test_fanout_feeds_every_recorder() -> None:
    from vault_agent.llm import TraceEvent

    seen_a: list[TraceEvent] = []
    seen_b: list[TraceEvent] = []
    event = TraceEvent(kind="backstop", backstop_id="fk_demotion")

    run_mod.fanout(seen_a.append, seen_b.append)(event)

    assert seen_a == [event] and seen_b == [event]


def test_run_metrics_carries_trace_path_and_backstop_fires() -> None:
    from vault_agent.state import VaultAgentState

    metrics = run_mod.run_metrics(
        VaultAgentState(),
        1.5,
        run_mod.UsageTotals(),
        Path("eval/results/bank/x.trace.jsonl"),
        {"attributes_without_cdk": 2},
    )

    assert metrics["trace_path"] == "eval/results/bank/x.trace.jsonl"
    assert metrics["backstop_fires"] == {"attributes_without_cdk": 2}
    # An un-instrumented call keeps the pre-WP15 shape apart from the (empty) fire map.
    plain = run_mod.run_metrics(VaultAgentState(), 1.5, run_mod.UsageTotals())
    assert "trace_path" not in plain and plain["backstop_fires"] == {}
