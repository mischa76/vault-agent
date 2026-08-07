"""WP29.2 — the stored probe, re-scored offline at zero cost.

The 2026-08-01 live probe answered nine concepts and cost ~$0.60. Its answers are frozen in
`tests/fixtures/resolution/probe_20260801_answers.json`, so the instrument can be re-tested
against real model output without a single new API call. That is this WP's acceptance: if the
scorers cannot read this run correctly, the join is still wrong, and finding that out is free.

What "correctly" means is pinned below, and it is NOT "everything passes" — the probe contains a
real false merge that the pre-WP29.2 matching could not see.
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.resolution import ResolutionResult, load_golden_resolution
from eval.scorers import false_merge_rate, resolution_accuracy
from vault_agent.state import ResolutionProposal

GOLDEN = Path("eval/datasets/brownfield_resolution/golden_resolution.yml")
ANSWERS = Path("tests/fixtures/resolution/probe_20260801_answers.json")


def _probe() -> ResolutionResult:
    raw = json.loads(ANSWERS.read_text(encoding="utf-8"))
    return ResolutionResult(proposals=[
        ResolutionProposal(
            concept=key,
            resolution=str(v.get("resolution", "unresolved")),
            same_as=v.get("same_as"),
            confidence=float(v.get("confidence", 0.0)),
            evidence=[str(e) for e in v.get("evidence", [])],
        )
        for key, v in sorted(raw.items())
    ])


def test_the_probe_is_scored_at_all() -> None:
    """The pre-WP29.2 failure: nothing matched, so the primary gate came back vacuous."""
    scored = false_merge_rate(load_golden_resolution(GOLDEN), _probe())

    assert "vacuous" not in scored.details, (
        "the instrument still cannot see the probe's merges: " + scored.details
    )


def test_the_probe_contains_a_real_false_merge_and_it_is_named() -> None:
    """`migration_assignment::crm_guid -> hub_customer` contradicts the golden on that key.

    The golden's trap 4 says a concept keyed on the CRM's internal GUID is a
    `same_as_candidate` and never a merge — the key spaces differ, so merging pushes CRM GUIDs
    into a hub keyed on the national customer ID. The resolver answered that correctly for
    `crm_kunde` and contradicted itself on the xref table's occurrence of the same key.

    This is the finding the table-based matching could not produce: with no match, the proposal
    was out of universe and passed unexamined."""
    scored = false_merge_rate(load_golden_resolution(GOLDEN), _probe())

    assert scored.score == 0.0, scored.details
    assert "crm_guid" in scored.details


def test_the_seven_golden_concepts_are_answered_but_one_is_contradicted() -> None:
    """Accuracy is 6/7, not 7/7 — and the missing one is the contradiction, not a wrong answer.

    Worth pinning precisely: every golden concept HAS a correct answer among the proposals, so
    a lenient scorer would read 7/7 and hide the contradiction. Agreement is required."""
    scored = resolution_accuracy(load_golden_resolution(GOLDEN), _probe())

    assert scored.score == 6 / 7, scored.details
    assert "crm_kunde" in scored.details and "disagree" in scored.details
    assert "hub_customer" in scored.details and "same_as_candidate" in scored.details


def test_a_missing_answer_never_scores_as_correct() -> None:
    """Kick-off §2: an unmatched golden entry used to read as `unresolved` — and trap 5 EXPECTS
    `unresolved`, so it scored as right having measured nothing."""
    scored = resolution_accuracy(load_golden_resolution(GOLDEN), ResolutionResult(proposals=[]))

    assert scored.score == 0.0, scored.details
