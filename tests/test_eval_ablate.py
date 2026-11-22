"""Keyless tests for the ablation runner (WP16 §2.4).

The live arms need an API key and are never executed here; ``run_case_once``/``_score_run``
are stubbed at the module seam (WP14.1 style), which is exactly what the crash-safety
property is about: each completed repeat must already be on disk when a later one fails.
"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval import ablate
from eval.datasets import EvalCase, Expectations, GoldenModel
from eval.scorers import ScorerResult
from vault_agent.rules.dv2_rules import excluded_rules
from vault_agent.state import ValidationIssue, ValidationReport


def _case() -> EvalCase:
    return EvalCase(
        name="synthetic",
        input_document="unused.md",
        golden=GoldenModel(),
        expectations=Expectations(),
    )


def _state(codes: list[str]) -> SimpleNamespace:
    issues = [
        ValidationIssue(severity="error", code=code, construct="sat_x", message="m")
        for code in codes
    ]
    return SimpleNamespace(
        validation_report=ValidationReport(passed=not codes, issues=issues)
    )


@pytest.fixture(autouse=True)
def _no_exclusions_leak():
    yield
    from vault_agent.rules.dv2_rules import set_excluded_rules

    set_excluded_rules(None)


def _stub(monkeypatch: pytest.MonkeyPatch, runs: list[object], score: float = 1.0) -> None:
    """Stub the run seam with a scripted sequence (a state, or an Exception to raise)."""
    pending = list(runs)

    async def fake_run_case_once(case: EvalCase) -> object:
        outcome = pending.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(ablate, "run_case_once", fake_run_case_once)
    monkeypatch.setattr(
        ablate, "_score_run", lambda case, state, golden: [ScorerResult(
            name="construct_f1", score=score, details="d"
        )]
    )


def _run(tmp_path: Path, rule: str = "cdk_not_payload", repeat: int = 2):
    return asyncio.run(
        ablate.run_ablation(
            _case(), None, rule,
            repeat=repeat, out_path=tmp_path / "ablation.json",
            models={"primary_model": "m", "heavy_model": "h"}, git_sha="abc",
            timestamp="20260722T000000000000Z",
        )
    )


def test_rule_by_id_rejects_an_unknown_rule() -> None:
    with pytest.raises(ValueError, match="unknown steering rule id"):
        ablate.rule_by_id("not_a_rule")


def test_issue_codes_counts_by_code() -> None:
    assert ablate.issue_codes(_state(["E_SAT_DUP_ATTR", "E_SAT_DUP_ATTR", "E_NO_HUBS"])) == {
        "E_SAT_DUP_ATTR": 2,
        "E_NO_HUBS": 1,
    }


def test_both_arms_run_and_the_report_carries_the_rule_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub(monkeypatch, [_state([]) for _ in range(4)])

    report, failure = _run(tmp_path)

    assert failure is None
    assert set(report["arms"]) == {"baseline", "dropped"}
    assert report["arms"]["baseline"]["repeats"] == 2
    assert report["arms"]["dropped"]["repeats"] == 2
    assert report["rule"] == "cdk_not_payload"
    assert report["backstop"] == "attributes_without_cdk"  # what the fire count refers to
    assert report["rule_text"].startswith("A multi-active satellite's child_dependent_key")
    on_disk = json.loads((tmp_path / "ablation.json").read_text())
    assert on_disk == report
    assert excluded_rules() == frozenset()  # the seam is always cleared


def test_a_failing_second_arm_leaves_the_first_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # WP14.1 semantics: an exhausted credit balance in the dropped arm must not discard the
    # baseline arm that was already paid for.
    _stub(
        monkeypatch,
        [_state([]), _state([]), RuntimeError("credit balance too low")],
    )

    report, failure = _run(tmp_path)

    assert failure == ("dropped", 1, "RuntimeError: credit balance too low")
    on_disk = json.loads((tmp_path / "ablation.json").read_text())
    assert on_disk["arms"]["baseline"]["repeats"] == 2
    assert on_disk["arms"]["dropped"]["repeats"] == 0
    assert excluded_rules() == frozenset()  # cleared even on the failure path


def test_summarise_arm_aggregates_scores_fires_and_codes() -> None:
    records = [
        {
            "scores": {"construct_f1": 1.0},
            "backstop_fires": {"attributes_without_cdk": 1},
            "validation_issue_codes": {"E_SAT_DUP_ATTR": 1},
            "validation_passed": False,
            "usage": {"input_tokens": 10, "output_tokens": 2},
        },
        {
            "scores": {"construct_f1": 0.5},
            "backstop_fires": {"attributes_without_cdk": 2},
            "validation_issue_codes": {},
            "validation_passed": True,
            "usage": {"input_tokens": 5, "output_tokens": 1},
        },
    ]
    summary = ablate.summarise_arm(records)

    assert summary["mean_scores"] == {"construct_f1": 0.75}
    assert summary["backstop_fires"] == {"attributes_without_cdk": 3}
    assert summary["validation_issue_codes"] == {"E_SAT_DUP_ATTR": 1}
    assert summary["validation_passed"] == [False, True]
    assert (summary["input_tokens"], summary["output_tokens"]) == (15, 3)


def test_render_comparison_calls_out_a_still_needed_rule() -> None:
    report = {
        "case": "health_insurance",
        "rule": "cdk_not_payload",
        "repeats": 3,
        "arms": {
            "baseline": {
                "mean_scores": {"construct_f1": 0.9},
                "backstop_fires": {},
                "validation_issue_codes": {},
            },
            "dropped": {
                "mean_scores": {"construct_f1": 0.6},
                "backstop_fires": {"attributes_without_cdk": 4},
                "validation_issue_codes": {"E_SAT_DUP_ATTR": 2},
            },
        },
    }
    text = ablate.render_comparison(report)

    assert "baseline" in text and "dropped" in text
    assert "construct_f1" in text and "0.900" in text and "0.600" in text
    assert "still earns its place" in text


def test_render_comparison_flags_a_candidate_delete() -> None:
    report = {
        "case": "bank",
        "rule": "unit_of_work",
        "repeats": 3,
        "arms": {
            "baseline": {"mean_scores": {"construct_f1": 0.9}, "backstop_fires": {},
                         "validation_issue_codes": {}},
            "dropped": {"mean_scores": {"construct_f1": 0.9}, "backstop_fires": {},
                        "validation_issue_codes": {}},
        },
    }
    assert "candidate-delete" in ablate.render_comparison(report)


def test_main_without_api_key_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ablate.main(["--case", "bank", "--drop", "cdk_not_payload"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
