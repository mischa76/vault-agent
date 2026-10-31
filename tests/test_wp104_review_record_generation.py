"""WP104 — the review record is per product generation (spec §2). Committed before the change,
failing: the 5.5 record's second generation begins at the twenty-second chain (WP79–WP99), the
first generation's judgements do not move, the 4.8 record stays one generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eval import wp34_check
from eval.wp34_check import REVIEW_DECISION_SAMPLES, check
from tests.test_wp34_check import _chain

TWENTY_SECOND = "20261030T184653194084Z"
ARCHIVED = Path(f"eval/results/adventureworks_incremental/{TWENTY_SECOND}-run1.json")
FIRST_GENERATION = (
    # stamp, decisions, the ceiling it was judged against, the chains before it (docs/log.md)
    ("20261011T115456381889Z", 83, "88.3", 3),  # seventeenth (the floor, re-checked under WP70)
    ("20261013T020131196768Z", 85, "88.2", 4),  # eighteenth
    ("20261017T163032109423Z", 88, "88.6", 5),  # twentieth
    ("20261017T203103850712Z", 87, "89.3", 6),  # twenty-first
)


def _five_five(decisions: int, stamp: str | None = None) -> dict[str, Any]:
    result = _chain(review_decisions=decisions)
    result["models"] = {"heavy_model": "claude-opus-5-5", "primary_model": "claude-sonnet-5-5"}
    if stamp is not None:
        result["timestamp"] = stamp
    return result


def _review_line(result: dict[str, Any]) -> tuple[bool, str]:
    held, lines = check(result)
    [line] = [ln for ln in lines if "review:" in ln]
    return held, line


def test_the_5_5_record_has_two_generations_and_keeps_every_sample() -> None:
    generations = wp34_check.REVIEW_GENERATIONS["claude-opus-5-5"]
    assert [since for since, _ in generations][-1] == TWENTY_SECOND
    assert all(label for _, label in generations)
    assert "claude-opus-4-8" not in wp34_check.REVIEW_GENERATIONS  # one generation, unlabelled
    # Nothing pruned: the eight 5.5 chains up to the twenty-second's 91, then the second
    # generation's samples as they are recorded (the twenty-third's 95, 2026-10-31).
    record = REVIEW_DECISION_SAMPLES["claude-opus-5-5"]
    assert [count for _, count in record][:8] == [84, 83, 83, 83, 85, 88, 87, 91]
    assert record[7][0] == TWENTY_SECOND
    assert all(stamp > TWENTY_SECOND for stamp, _ in record[8:])


@pytest.mark.skipif(not ARCHIVED.exists(), reason="the archived result is not in this checkout")
def test_the_twenty_second_chain_seeds_its_generation_and_is_no_longer_judged() -> None:
    held, line = _review_line(json.loads(ARCHIVED.read_text(encoding="utf-8")))
    assert not held
    assert "91 decision(s)" in line and "cannot be judged" in line
    assert "0 recorded chain(s)" in line
    [(_, label)] = wp34_check.REVIEW_GENERATIONS["claude-opus-5-5"][-1:]
    assert label in line


def test_an_unrecorded_5_5_chain_is_judged_against_the_second_generation() -> None:
    held, line = _review_line(_five_five(86))
    second = [s for s, _ in REVIEW_DECISION_SAMPLES["claude-opus-5-5"] if s >= TWENTY_SECOND]
    if len(second) < wp34_check.MIN_REVIEW_SAMPLES:
        assert not held and "cannot be judged" in line
        assert f"{len(second)} recorded chain(s), need 3" in line
    else:  # from the twenty-fifth on the generation judges
        assert f"{len(second)} recorded chain(s)" in line and "generation" in line


@pytest.mark.parametrize(("stamp", "decisions", "ceiling", "before"), FIRST_GENERATION)
def test_the_first_generations_judgements_do_not_move(
    stamp: str, decisions: int, ceiling: str, before: int
) -> None:
    held, line = _review_line(_five_five(decisions, stamp))
    assert held and "HELD" in line, line
    assert ceiling in line and f"{before} recorded chain(s)" in line, line


def test_a_chain_before_the_boundary_is_judged_by_the_whole_first_generation() -> None:
    # Stamped after the twenty-first and before the twenty-second: still the first generation,
    # all seven chains before it, the ceiling the twenty-second failed.
    held, line = _review_line(_five_five(91, "20261020T000000000000Z"))
    assert not held and "FAILED" in line
    assert "89.7" in line and "7 recorded chain(s)" in line


def test_the_4_8_record_is_one_generation_without_a_label() -> None:
    held, line = _review_line(_chain(review_decisions=140))
    assert held and "11 recorded chain(s)" in line
    assert "generation" not in line
