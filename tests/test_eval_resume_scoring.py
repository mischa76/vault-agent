"""A resumed chain is scored from its persisted steps, not from their reconstructed states
(2026-10-07, the seventh chain). Committed before the change, failing.

A resumed step's state carries its model and nothing else (2026-09-13), so WP52's
minimum-over-steps read an empty validation report (gate 0.0) and the chain's review counts
summed only the steps actually run (42 of 127). The step result files hold the real numbers.
"""
from __future__ import annotations

from typing import Any

from eval.datasets import DATASETS_ROOT, load_eval_case
from eval.run import UsageTotals, chain_metrics, score_chain
from tests.test_wp52_three_quick_wins import _clean
from vault_agent.state import DVModel, VaultAgentState


def _resumed(hubs: list[str]) -> VaultAgentState:
    """What run_chain_once builds for a resumed step: the model, nothing else."""
    return VaultAgentState(dv_model=_clean(hubs).dv_model)


def _persisted(decisions: int) -> dict[str, Any]:
    """The shape of a persisted step result: top-level scores and metrics."""
    return {
        "scores": {
            "validation_gate": 1.0, "pipeline_health": 1.0,
            "existing_construct_preservation": 1.0,
        },
        "metrics": {
            "review_items_total": decisions + 5, "review_decisions": decisions,
            "review_disclosures": 5, "review_queue_lines": 9,
            "constructs": {"hubs": 1, "links": 0, "satellites": 1},
            "model": {"hubs": ["hub_a"], "links": [], "satellites": ["sat_a"]},
        },
    }


def test_a_resumed_step_is_scored_from_its_persisted_result() -> None:
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    chain = [(case, _resumed(["hub_a"])), (case, _clean(["hub_a", "hub_b"]))]
    results = score_chain(case, chain, None, persisted={1: _persisted(14)})
    by_name = {r.name: r for r in results}
    assert by_name["validation_gate"].score == 1.0
    assert by_name["pipeline_health"].score == 1.0
    assert "persisted" in by_name["validation_gate"].details


def test_a_resumed_steps_review_counts_come_from_its_persisted_result() -> None:
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    chain = [(case, _resumed(["hub_a"])), (case, _clean(["hub_a", "hub_b"]))]
    metrics = chain_metrics(chain, 1.0, UsageTotals(), None, {}, persisted={1: _persisted(14)})
    assert metrics["chain_steps"][0]["review_decisions"] == 14
    assert metrics["chain_steps"][0]["review_items"] == 19
    assert metrics["review_decisions"] == 14 + metrics["chain_steps"][1]["review_decisions"]
    assert metrics["chain_steps"][0]["model"] == {
        "hubs": ["hub_a"], "links": [], "satellites": ["sat_a"]
    }
