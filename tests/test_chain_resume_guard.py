"""Guard written FIRST, 2026-09-13: a chain that died can be resumed at the step that died.

Repeat 2 of the WP30 rerun (`20260913T031718223484Z`) lost step 5 to an exhausted API credit.
Steps 1–4 were on disk as result JSON — scores, metrics, `hub_keys` — but the model itself, the
`metadata/dv_model.yml` the next step reads, lived in the eval's temporary workdir and was gone
with it. Four paid steps could not be continued; the whole chain (~$6.4) had to be bought again.

Two pins: (1) each completed step leaves its model beside its result, in the CLI's own artifact
form; (2) `--resume-chain <stamp>` runs only the steps that stamp has no model for, threading the
persisted model into the first step it runs, and the result says what was resumed.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from eval import run as run_mod
from eval.datasets import DATASETS_ROOT, EvalCase, load_eval_case
from vault_agent.existing_model import load_existing_model
from vault_agent.state import DVModel, Hub, VaultAgentState

MODELS = {"primary_model": "m", "heavy_model": "h"}


def _hub(name: str) -> Hub:
    return Hub(name=name, business_key="id", source_entity=name, description=name)


def _stub_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_mod, "_score_run", lambda case, state, golden: [])
    monkeypatch.setattr(run_mod, "run_metrics", lambda *a, **k: {"wall_clock_seconds": 1.0})


def _die_at(step: int, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}

    async def fake(case: EvalCase) -> VaultAgentState:
        calls["n"] += 1
        if calls["n"] == step:
            raise RuntimeError("credit balance too low")
        return VaultAgentState(dv_model=DVModel(hubs=[_hub(f"hub_step{calls['n']}")]))

    monkeypatch.setattr(run_mod, "run_case_once", fake)
    return calls


def test_a_dying_chain_leaves_each_completed_step_model_beside_its_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_scoring(monkeypatch)
    _die_at(3, monkeypatch)
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    asyncio.run(run_mod._run_score_write(
        case, None, 1, out_root=tmp_path, models=MODELS, git_sha="abc",
    ))
    models = sorted((tmp_path / case.name).glob("*step*.dv_model.yml"))
    assert [p.name.split("-", 1)[1] for p in models] == [
        "step1-adventureworks_person-run1.dv_model.yml",
        "step2-adventureworks_humanresources-run1.dv_model.yml",
    ]
    reloaded = load_existing_model(models[1])
    assert reloaded is not None and [h.name for h in reloaded.hubs] == ["hub_step2"]


def test_resuming_runs_only_the_missing_steps_from_the_persisted_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_scoring(monkeypatch)
    _die_at(3, monkeypatch)
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    asyncio.run(run_mod._run_score_write(
        case, None, 1, out_root=tmp_path, models=MODELS, git_sha="abc",
    ))
    stamp = next((tmp_path / case.name).glob("*step1*.json")).name.split("-step1")[0]

    seen_existing: list[list[str]] = []

    async def fake(case: EvalCase) -> VaultAgentState:
        existing = load_existing_model(case.existing) if case.existing else None
        seen_existing.append([h.name for h in existing.hubs] if existing else [])
        return VaultAgentState(dv_model=DVModel(hubs=[_hub(f"hub_new{len(seen_existing)}")]))

    monkeypatch.setattr(run_mod, "run_case_once", fake)
    runs, metrics, written, failure = asyncio.run(run_mod._run_score_write(
        case, None, 1, out_root=tmp_path, models=MODELS, git_sha="abc",
        resume_chain=stamp,
    ))
    assert failure is None and len(written) == 1
    # Steps 3, 4, 5 ran; step 3 read step 2's persisted model as its existing vault.
    assert seen_existing[0] == ["hub_step2"] and len(seen_existing) == 3
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["metrics"]["resumed_from"] == {"stamp": stamp, "steps": [1, 2]}
    assert [s["case"] for s in payload["metrics"]["chain_steps"]][:2] == [
        "adventureworks_person", "adventureworks_humanresources",
    ]
