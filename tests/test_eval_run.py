"""Keyless tests for the live runner's pure helpers (WP6 layer 3).

The runner itself needs an API key and is never executed here — these tests cover the
deterministic parts: aggregation, the min_scores gate, the JSON payload, the report
table, and the missing-key guard."""
import pytest

from eval.datasets import EvalCase, Expectations, GoldenModel
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
