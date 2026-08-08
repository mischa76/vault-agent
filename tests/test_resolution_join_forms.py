"""WP29.5 — the concept join, against every form the pipeline has actually emitted.

The field half of a concept key is LLM free text that usually looks like a column name. Across
all traces on disk (79 distinct field expressions from 11 §4 runs plus the WP30 arm chains) it
takes exactly three shapes, and the join has to survive all of them:

    plain        partn_nr
    gloss        partn_nr (national customer number)
    composite    crm_guid + partn_nr            (optionally also glossed)

WP29.2 anchored the join on the column believing the field WAS one. Two of five clean §4 repeats
then scored 0.000 while answering all seven traps correctly, because that run's identifier
glossed every field. This is the fifth appearance of the class `.claude/rules/eval.md` puts
first, so the fix is measured against the recorded forms rather than against the one that bit.

The runs are frozen in `tests/fixtures/resolution/section4_runs.json` — real model output,
re-scored offline. Fixing this cost no API calls at all.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.resolution import ResolutionResult, key_ref, load_golden_resolution
from eval.scorers import resolution_accuracy
from vault_agent.state import ResolutionProposal

GOLDEN = Path("eval/datasets/brownfield_resolution/golden_resolution.yml")
RUNS = Path("tests/fixtures/resolution/section4_runs.json")


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("partner::partn_nr", "PARTN_NR"),
        # A gloss is trailing and parenthetical by convention. Without stripping it,
        # normalize_identifier folds it in: PARTN_NR_NATIONAL_CUSTOMER_NUMBER.
        ("partner::partn_nr (national customer number)", "PARTN_NR"),
        ("legacy_holding::alt_nr (legacy number)", "ALT_NR"),
        # A COMPOSITE key is deliberately NOT reduced to one of its parts. The golden judges a
        # concept keyed on `crm_guid`; a concept keyed on `crm_guid + partn_nr` is keyed on
        # something else, and matching it to either part would conflate two concepts — the
        # WP24/WP32 defect, re-entered from the other side. It stays out of universe.
        ("xref::crm_guid + partn_nr", "CRM_GUID_PARTN_NR"),
        ("xref::crm_guid + partn_nr (composite cross-reference key)", "CRM_GUID_PARTN_NR"),
        ("d::BusinessEntityID + CreditCardID", "BUSINESSENTITYID_CREDITCARDID"),
    ],
)
def test_key_ref_handles_every_recorded_form(field: str, expected: str) -> None:
    assert key_ref(field) == expected


def _runs() -> dict[str, dict[str, dict[str, object]]]:
    return json.loads(RUNS.read_text(encoding="utf-8"))


def _result(answers: dict[str, dict[str, object]]) -> ResolutionResult:
    return ResolutionResult(proposals=[
        ResolutionProposal(
            concept=key,
            resolution=str(v.get("resolution", "unresolved")),
            same_as=v.get("same_as"),  # type: ignore[arg-type]
            confidence=float(v.get("confidence", 0.0)),  # type: ignore[arg-type]
        )
        for key, v in sorted(answers.items())
    ])


def test_every_clean_section4_repeat_scores_a_perfect_seven() -> None:
    """The acceptance, and it is free: all five 2026-08-08 clean runs answered 7/7 correctly.

    Three of them scored 1.000 and two scored 0.000 — the difference was the gloss, not the
    mechanism. If any repeat still falls short after the fix, the join is still reading the
    text rather than the key."""
    golden = load_golden_resolution(GOLDEN)
    scored = {
        name.split("/")[-1]: resolution_accuracy(golden, _result(answers))
        for name, answers in _runs().items()
        if name.startswith("brownfield_resolution/20260808")
    }

    assert len(scored) == 5, f"expected the five clean repeats, got {sorted(scored)}"
    wrong = {k: (v.score, v.details) for k, v in scored.items() if v.score != 1.0}
    assert not wrong, f"clean repeats not scoring 7/7: {wrong}"


def test_the_blinded_repeats_are_unchanged_by_the_fix() -> None:
    """The blinded runs carry no gloss, so their scores must not move.

    Pinned because a join loose enough to rescue the glossed runs could also start matching
    things it should not — and the blinded numbers are the ones §4 acceptance #3 rests on."""
    golden = load_golden_resolution(GOLDEN)
    scores = sorted(
        round(resolution_accuracy(golden, _result(answers)).score, 3)
        for name, answers in _runs().items()
        if name.startswith("brownfield_resolution_blind/")
    )

    assert scores == [0.429, 0.429, 0.429, 0.429, 0.571], scores
