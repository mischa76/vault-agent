"""Pinned tests for the entity-resolution scorers (brownfield Phase 2 spike, D2). No API key.

The load-bearing property under test is the ASYMMETRY the spike charter §2 sets: a false
merge is a hard failure, an honest ``unresolved`` is not, and the two must never be averaged
into one number.
"""
from pathlib import Path

import pytest

from eval.resolution import (
    GoldenConstruct,
    GoldenResolution,
    GoldenResolutionSet,
    ProposedResolution,
    ResolutionResult,
    load_golden_resolution,
)
from eval.scorers import (
    VACUOUS_PREFIX,
    false_merge_rate,
    new_hub_detection,
    resolution_accuracy,
    resolution_calibration,
)

_GOLDEN_FILE = (
    Path(__file__).parents[1] / "eval" / "datasets" / "brownfield_resolution"
    / "golden_resolution.yml"
)


def _golden() -> GoldenResolutionSet:
    return GoldenResolutionSet(
        existing_constructs=[
            GoldenConstruct(name="hub_customer", business_key="national customer ID"),
            GoldenConstruct(name="hub_account", business_key="account number"),
        ],
        resolutions=[
            GoldenResolution(concept="partner", source_table="vic_partner",
                             source_key="partn_nr", expected="hub_customer"),
            GoldenResolution(concept="kontakt", source_table="vic_kontakt",
                             source_key="kontakt_id", expected="NEW"),
            GoldenResolution(concept="crm_kunde", source_table="crm_kunde",
                             source_key="crm_guid", expected="same_as_candidate",
                             same_as="hub_customer"),
        ],
    )


def _result(**answers: str) -> ResolutionResult:
    return ResolutionResult(
        proposals=[
            ProposedResolution(concept=c, resolution=r, confidence=0.9)
            for c, r in answers.items()
        ]
    )


# ── the primary metric ────────────────────────────────────────────────────────────────────
def test_correct_merges_score_one() -> None:
    result = false_merge_rate(_golden(), _result(partner="hub_customer", kontakt="NEW"))

    assert result.score == 1.0
    assert "no foreign key entered an existing hub" in result.details


def test_a_single_false_merge_drops_the_score_to_zero_and_names_it() -> None:
    """The false friend merged into the customer hub — the cardinal sin."""
    result = false_merge_rate(_golden(), _result(kontakt="hub_customer"))

    assert result.score == 0.0
    assert "FALSE MERGE" in result.details
    assert "kontakt -> hub_customer (golden: NEW)" in result.details


def test_merging_onto_the_wrong_existing_construct_counts_as_a_false_merge() -> None:
    result = false_merge_rate(_golden(), _result(partner="hub_account"))

    assert result.score == 0.0


def test_unresolved_is_never_a_false_merge() -> None:
    """The honest non-answer is the behaviour we want when the mechanism cannot tell."""
    result = false_merge_rate(_golden(), _result(partner="unresolved", kontakt="unresolved"))

    assert result.score == 1.0
    assert result.details.startswith(VACUOUS_PREFIX)


def test_a_same_as_candidate_is_not_a_merge() -> None:
    """Two constructs plus a flag — the charter's required output, not a merge."""
    result = false_merge_rate(_golden(), _result(crm_kunde="same_as_candidate"))

    assert result.score == 1.0


# ── the secondary metrics, and why they are separate ──────────────────────────────────────
def test_accuracy_and_merge_safety_disagree_on_an_unhelpful_mechanism() -> None:
    """A mechanism that answers `unresolved` to everything is SAFE and USELESS. The two
    scores must show that, which is why they are never averaged."""
    everything_unresolved = _result(
        partner="unresolved", kontakt="unresolved", crm_kunde="unresolved"
    )

    assert false_merge_rate(_golden(), everything_unresolved).score == 1.0
    assert resolution_accuracy(_golden(), everything_unresolved).score == 0.0


def test_accuracy_and_merge_safety_disagree_on_a_dangerous_mechanism() -> None:
    """And the mirror image: mostly right, but it merged the false friend."""
    dangerous = ResolutionResult(proposals=[
        ProposedResolution(concept="partner", resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept="kontakt", resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept="crm_kunde", resolution="same_as_candidate",
                           same_as="hub_customer", confidence=0.9),
    ])

    assert resolution_accuracy(_golden(), dangerous).score == pytest.approx(2 / 3)
    assert false_merge_rate(_golden(), dangerous).score == 0.0


def test_a_same_as_pointing_at_the_wrong_construct_is_not_accurate() -> None:
    result = ResolutionResult(proposals=[
        ProposedResolution(concept="crm_kunde", resolution="same_as_candidate",
                           same_as="hub_account")
    ])

    assert "crm_kunde" in resolution_accuracy(_golden(), result).details


def test_new_hub_detection_catches_the_trivially_safe_mechanism() -> None:
    """false_merge_rate alone can be gamed by never merging; this is what notices."""
    never_merges = _result(partner="NEW", kontakt="unresolved", crm_kunde="unresolved")

    assert false_merge_rate(_golden(), never_merges).score == 1.0
    assert new_hub_detection(_golden(), never_merges).score == 0.0  # 0 of 2 identified


def test_new_hub_detection_counts_only_the_non_merge_concepts() -> None:
    result = ResolutionResult(proposals=[
        ProposedResolution(concept="partner", resolution="hub_customer"),
        ProposedResolution(concept="kontakt", resolution="NEW"),
        ProposedResolution(concept="crm_kunde", resolution="same_as_candidate",
                           same_as="hub_customer"),
    ])

    assert new_hub_detection(_golden(), result).score == 1.0


# ── calibration ───────────────────────────────────────────────────────────────────────────
def test_calibration_measures_the_margin_between_right_and_wrong() -> None:
    result = ResolutionResult(proposals=[
        ProposedResolution(concept="partner", resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept="kontakt", resolution="hub_customer", confidence=0.3),
    ])

    assert resolution_calibration(_golden(), result).score == pytest.approx(0.6)


def test_calibration_is_vacuous_when_nothing_is_wrong() -> None:
    scored = resolution_calibration(_golden(), _result(partner="hub_customer"))

    assert scored.score == 1.0 and scored.details.startswith(VACUOUS_PREFIX)


# ── the shipped golden set ────────────────────────────────────────────────────────────────
def test_the_shipped_golden_set_loads_and_covers_every_trap_class() -> None:
    golden = load_golden_resolution(_GOLDEN_FILE)

    traps = {entry.trap for entry in golden.resolutions}
    assert {"synonym_hub", "false_friend", "similar_name_new_hub", "same_as"} <= traps
    # The discriminating pair: two concepts sharing the PARTNER stem, opposite answers.
    by_concept = golden.by_concept()
    assert by_concept["partner"].expected == "hub_customer"
    assert by_concept["vertragspartner"].expected == "NEW"


def test_the_loader_rejects_a_golden_naming_an_unknown_construct(tmp_path: Path) -> None:
    path = tmp_path / "golden.yml"
    path.write_text(
        "existing_constructs: [{name: hub_a, business_key: a}]\n"
        "resolutions: [{concept: c, source_table: t, source_key: k, expected: hub_nope}]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="neither a declared existing construct"):
        load_golden_resolution(path)


def test_the_loader_rejects_a_same_as_without_a_valid_target(tmp_path: Path) -> None:
    path = tmp_path / "golden.yml"
    path.write_text(
        "existing_constructs: [{name: hub_a, business_key: a}]\n"
        "resolutions: [{concept: c, source_table: t, source_key: k, "
        "expected: same_as_candidate}]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="`same_as` target"):
        load_golden_resolution(path)
