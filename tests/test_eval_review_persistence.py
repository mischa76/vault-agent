"""The eval persists each run's review queue and its typed flags beside the result JSON.

Written first, failing. On 2026-09-13 the queue of a paid chain vanished with its tempdir; on
2026-10-03 the WP43 pre-registration had to be computed from saved counts because no run's
flags were on disk. From now on every result JSON has two siblings: ``<stem>.review-queue.md``
(the rendered checkpoint, byte-identical to what the CLI writes) and ``<stem>.review.json``
(the typed flags, validation issues, retirements and the queue with its roles), so a later
question about a paid run is answered from disk, never by paying again.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from eval import run as run_mod
from eval.datasets import EvalCase, Expectations, GoldenModel
from eval.run import review_artifact_paths, write_review_artifacts
from eval.scorers import ScorerResult
from vault_agent.agents.orchestrator import assemble_review_queue, render_review_queue_md
from vault_agent.state import (
    Artifacts,
    FlagKind,
    PipelineFlag,
    RetiredConstruct,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)


def _state() -> VaultAgentState:
    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=False,
            issues=[
                ValidationIssue(severity="error", code="E_NO_HUBS", construct="dv_model",
                                message="no hubs"),
                ValidationIssue(severity="warning", code="W_HUB_NO_SAT", construct="hub_a",
                                message="no satellite"),
                ValidationIssue(severity="info", code="I_EXISTING_EXTENDED", construct="hub_b",
                                message="new hub"),
            ],
        ),
        artifacts=Artifacts(
            contracts=[{"name": "customer", "owner": {"name": "TODO: assign", "email": None}}]
        ),
        retired_constructs=[
            RetiredConstruct(name="hub_x", kind="hub", code="E_HUB_HK_COLLISION", attempt=1)
        ],
    )
    state.flag("code_generator", "inferred", kind=FlagKind.SOURCE_BINDING, asset="stg_a")
    state.flag("link_proposer", "join through b", kind=FlagKind.LINK_TRANSLATION, asset="link_ab")
    return state


def test_artifact_paths_sit_beside_the_result_json(tmp_path: Path) -> None:
    md, js = review_artifact_paths(tmp_path, "20261004T000000000000Z-step2-sales-run1")
    assert md == tmp_path / "20261004T000000000000Z-step2-sales-run1.review-queue.md"
    assert js == tmp_path / "20261004T000000000000Z-step2-sales-run1.review.json"


def test_write_review_artifacts_round_trips_the_typed_content(tmp_path: Path) -> None:
    state = _state()
    md_path, json_path = write_review_artifacts(state, tmp_path, "stem")

    assert md_path.read_text(encoding="utf-8") == render_review_queue_md(
        assemble_review_queue(state)
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert [PipelineFlag.model_validate(f) for f in data["flags"]] == state.flags
    assert [ValidationIssue.model_validate(i) for i in data["issues"]] == (
        state.validation_report.issues
    )
    assert [RetiredConstruct.model_validate(r) for r in data["retired_constructs"]] == (
        state.retired_constructs
    )
    queue = assemble_review_queue(state)
    assert data["queue"]["decisions"] == len(queue.decisions)
    assert data["queue"]["disclosures"] == len(queue.disclosures)
    assert len(data["queue"]["items"]) == len(queue.items)
    assert {item["role"] for item in data["queue"]["items"]} == {"decision", "disclosure"}
    # The info record is in the issues (the inventory is kept) and not a queue item (WP43).
    assert any(i["severity"] == "info" for i in data["issues"])
    assert all("I_EXISTING_EXTENDED" not in item["summary"] for item in data["queue"]["items"])


def _case() -> EvalCase:
    return EvalCase(
        name="synthetic", input_document="unused.md", golden=GoldenModel(),
        expectations=Expectations(min_scores={}),
    )


def test_run_score_write_leaves_the_review_artifacts_beside_each_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_case_once(case: EvalCase) -> VaultAgentState:
        return _state()

    monkeypatch.setattr(run_mod, "run_case_once", fake_run_case_once)
    monkeypatch.setattr(
        run_mod, "_score_run",
        lambda case, state, golden: [ScorerResult(name="construct_f1", score=0.5, details="d")],
    )
    monkeypatch.setattr(run_mod, "run_metrics", lambda *a, **k: {"wall_clock_seconds": 1.0})

    _, _, written, failure = asyncio.run(
        run_mod._run_score_write(
            _case(), None, 2,
            out_root=tmp_path, models={"primary_model": "m", "heavy_model": "h"}, git_sha="abc",
        )
    )
    assert failure is None and len(written) == 2
    for result_path in written:
        stem = result_path.name.removesuffix(".json")
        md, js = review_artifact_paths(result_path.parent, stem)
        assert md.is_file() and js.is_file()
        assert json.loads(js.read_text(encoding="utf-8"))["queue"]["decisions"] == 3
