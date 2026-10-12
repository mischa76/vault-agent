"""WP70 — the review ceiling gets a floor of mean + REVIEW_TOLERANCE (spec §3). Committed
before the change, failing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import wp34_check
from eval.wp34_check import REVIEW_TOLERANCE, check, review_ceiling
from tests.test_wp34_check import _chain

FIRST_FIVE_4X = [148, 135, 142, 138, 139]
FIVE_FIVE = [84, 83, 83, 83]
SEVENTEENTH = Path("eval/results/adventureworks_incremental/20261011T115456381889Z-run1.json")


def test_the_floor_lifts_a_tight_record_and_never_lowers_a_wide_one() -> None:
    assert REVIEW_TOLERANCE == 5
    assert review_ceiling(FIVE_FIVE) == pytest.approx(88.25, abs=0.01)
    assert review_ceiling(FIRST_FIVE_4X) == pytest.approx(151.9, abs=0.1)


def test_the_report_line_names_which_bound_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wp34_check, "REVIEW_DECISION_SAMPLES", {
        "claude-opus-4-8": tuple((f"2026100{i}T000000000000Z", n) for i, n in enumerate(FIRST_FIVE_4X)),
        "claude-opus-5-5": tuple((f"2026100{i}T000000000000Z", n) for i, n in enumerate(FIVE_FIVE)),
    })
    tight = _chain(review_decisions=86)
    tight["models"] = {"heavy_model": "claude-opus-5-5"}
    held, lines = check(tight)
    [line] = [ln for ln in lines if "review:" in ln]
    assert held and "HELD" in line and "floor" in line and "88.2" in line
    wide = _chain(review_decisions=150)
    wide["models"] = {"heavy_model": "claude-opus-4-8"}
    held, lines = check(wide)
    [line] = [ln for ln in lines if "review:" in ln]
    assert held and "t-bound" in line and "151.9" in line


@pytest.mark.skipif(not SEVENTEENTH.exists(), reason="the archived result is not in this checkout")
def test_the_seventeenth_chain_holds_against_the_floor() -> None:
    result = json.loads(SEVENTEENTH.read_text(encoding="utf-8"))
    held, lines = check(result)
    [line] = [ln for ln in lines if "review:" in ln]
    assert "83 decision(s)" in line and "88.3" in line and "floor" in line and "HELD" in line
