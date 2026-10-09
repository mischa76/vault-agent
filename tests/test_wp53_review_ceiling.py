"""WP53 — the review ceiling becomes a distribution (spec §3). Committed before the change,
failing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eval import wp34_check
from eval.wp34_check import REVIEW_DECISION_SAMPLES as _RECORDS
from eval.wp34_check import check, review_ceiling

REVIEW_DECISION_SAMPLES = _RECORDS["claude-opus-4-8"]  # WP62: the record is per modeler model
from tests.test_wp34_check import _chain

FIRST_FIVE = [148, 135, 142, 138, 139]
SIXTH_STAMP = "20261006T172859787765Z"


def test_the_ceiling_is_the_one_sided_prediction_bound_over_the_samples() -> None:
    assert review_ceiling(FIRST_FIVE) == pytest.approx(151.9, abs=0.1)
    assert review_ceiling([*FIRST_FIVE, 156]) == pytest.approx(159.9, abs=0.1)


def test_a_judged_run_is_excluded_from_its_own_distribution() -> None:
    sixth: dict[str, Any] = _chain(review_decisions=156)
    sixth["timestamp"] = SIXTH_STAMP
    held, lines = check(sixth)
    [line] = [ln for ln in lines if "review:" in ln]
    assert not held and "FAILED" in line
    assert "5 recorded chain(s)" in line and "excluded" in line

    # No stamp — a chain not yet recorded — judged against the whole record; the record's own
    # mean always holds (the 156 used until 2026-10-09 stopped holding as the record tightened).
    mean = int(sum(c for _, c in REVIEW_DECISION_SAMPLES) / len(REVIEW_DECISION_SAMPLES))
    unrecorded = _chain(review_decisions=mean)
    held, lines = check(unrecorded)
    [line] = [ln for ln in lines if "review:" in ln]
    assert held and "HELD" in line
    assert f"{len(REVIEW_DECISION_SAMPLES)} recorded chain(s)" in line


def test_fewer_than_three_samples_cannot_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wp34_check, "REVIEW_DECISION_SAMPLES", {"claude-opus-4-8": REVIEW_DECISION_SAMPLES[:2]}
    )
    held, lines = check(_chain(review_decisions=140))
    [line] = [ln for ln in lines if "review:" in ln]
    assert not held and "FAILED" in line and "cannot be judged" in line


def _decisions_on_disk(root: Path, result: dict[str, Any]) -> int:
    """A chain's decisions: the sum over its step files. A chain resumed from an earlier
    stamp (`metrics.resumed_from`) has its leading steps under that stamp — and, before
    2026-10-07's fix, a chain-level count that summed only the steps it ran itself."""
    resumed = result["metrics"].get("resumed_from")
    per_step: dict[int, int] = {}
    for stamp in ([resumed["stamp"]] if resumed else []) + [result["timestamp"]]:
        for path in root.glob(f"{stamp}-step*-run1.json"):
            index = int(path.name.split("-step")[1].split("-")[0])
            per_step.setdefault(index, json.loads(path.read_text())["metrics"]["review_decisions"])
    return sum(per_step.values())


def test_the_recorded_samples_match_the_result_files_on_disk() -> None:
    root = Path("eval/results/adventureworks_incremental")
    seen = 0
    for stamp, decisions in REVIEW_DECISION_SAMPLES:
        path = root / f"{stamp}-run1.json"
        if not path.exists():
            continue
        seen += 1
        assert _decisions_on_disk(root, json.loads(path.read_text())) == decisions, stamp
    if seen == 0:
        pytest.skip("no archived chain results on this machine")
