"""Pinned-score tests for the mapping spike scorers and golden loader (charter D2). No API key.

Covers the three scorers (``mapping_accuracy``, ``gap_detection``,
``confidence_calibration``) over hand-built ``ProposedMapping`` results, plus the real
``messy_insurance/golden_mapping.yml`` loading and its §4 trap invariants.
"""
import math

import pytest

from eval.datasets import DATASETS_ROOT
from eval.mapping import (
    AmbiguousEntry,
    FalseFriend,
    GapEntry,
    GoldenCandidate,
    GoldenMapping,
    GoldenMappingEntry,
    Proposal,
    ProposedMapping,
    concepts_for_prototype,
    load_golden_mapping,
)
from eval.scorers import (
    MAPPING_SCORERS,
    confidence_calibration,
    gap_detection,
    mapping_accuracy,
    score_mapping,
)

GOLDEN_PATH = DATASETS_ROOT / "messy_insurance" / "golden_mapping.yml"


def _golden() -> GoldenMapping:
    """A small synthetic golden set exercising every branch: plain, ambiguous, gap, friend."""
    return GoldenMapping(
        mappings=[
            GoldenMappingEntry(
                concept="partner number",
                entity="partner",
                source_table="VICTOR_PARTNER",
                source_column="PARTN_NR",
                kind="business_key",
            ),
            GoldenMappingEntry(
                concept="city",
                entity="partner",
                source_table="VICTOR_PARTNER",
                source_column="KD_ORT",
            ),
        ],
        ambiguous=[
            AmbiguousEntry(
                concept="customer reference",
                entity="partner",
                candidates=[
                    GoldenCandidate(table="VICTOR_PARTNER", column="PARTN_NR"),
                    GoldenCandidate(table="CRM_ACCOUNT", column="ExternalCustomerNo"),
                ],
            )
        ],
        gaps=[GapEntry(concept="Schadenquote je Partner", reason="derived KPI")],
        false_friends=[FalseFriend(table="VICTOR_PARTNER", column="KD_NR", note="branch code")],
    )


# ── mapping_accuracy ────────────────────────────────────────────────────────────────────
def test_mapping_accuracy_all_correct_is_one() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="partner number", table="victor_partner", column="partn_nr"),
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT"),
            # ambiguous: the OTHER legitimate candidate still counts
            Proposal(
                concept="customer reference", table="CRM_ACCOUNT", column="ExternalCustomerNo"
            ),
        ]
    )
    result = mapping_accuracy(proposed, golden)
    assert result.score == pytest.approx(1.0)  # 3/3 precision, 3/3 recall


def test_mapping_accuracy_penalises_false_friend_and_names_it() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            # false friend: KD_NR is a branch code, not a customer number
            Proposal(concept="partner number", table="VICTOR_PARTNER", column="KD_NR"),
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT"),
        ]
    )
    result = mapping_accuracy(proposed, golden)
    # precision 1/2, recall 1/3 (only "city" correct); F1 = 2*.5*.333/(.5+.333)
    assert result.score == pytest.approx(2 * 0.5 * (1 / 3) / (0.5 + 1 / 3))
    assert "FALSE-FRIEND HIT" in result.details
    assert "KD_NR" in result.details


def test_mapping_accuracy_gap_force_fit_hurts_precision() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="partner number", table="VICTOR_PARTNER", column="PARTN_NR"),
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT"),
            Proposal(concept="customer reference", table="VICTOR_PARTNER", column="PARTN_NR"),
            # force-fit a gap concept onto a column: a wrong proposal
            Proposal(concept="Schadenquote je Partner", table="VICTOR_PARTNER", column="PARTN_NR"),
        ]
    )
    result = mapping_accuracy(proposed, golden)
    # 3 correct / 4 proposals precision, 3/3 recall
    precision, recall = 3 / 4, 1.0
    assert result.score == pytest.approx(2 * precision * recall / (precision + recall))


def test_mapping_accuracy_vacuous_when_empty() -> None:
    assert mapping_accuracy(ProposedMapping(), GoldenMapping()).score == pytest.approx(1.0)


# ── gap_detection ───────────────────────────────────────────────────────────────────────
def test_gap_detection_full_recall() -> None:
    golden = _golden()
    proposed = ProposedMapping(gaps=["Schadenquote je Partner"])
    result = gap_detection(proposed, golden)
    assert result.score == pytest.approx(1.0)


def test_gap_detection_force_fit_named_and_zero_recall() -> None:
    golden = _golden()
    # the gap concept was mapped instead of gap-flagged: recall 0, force-fit named
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="Schadenquote je Partner", table="VICTOR_PARTNER", column="PARTN_NR")
        ]
    )
    result = gap_detection(proposed, golden)
    assert result.score == pytest.approx(0.0)
    assert "FORCE-FIT" in result.details
    assert "Schadenquote je Partner" in result.details


def test_gap_detection_unresolved_is_not_force_fit() -> None:
    golden = _golden()
    proposed = ProposedMapping(unresolved=["Schadenquote je Partner"])
    result = gap_detection(proposed, golden)
    assert result.score == pytest.approx(0.0)  # honest miss, but not caught as a gap
    assert "FORCE-FIT" not in result.details


def test_gap_detection_vacuous_without_golden_gaps() -> None:
    golden = GoldenMapping(mappings=[])
    assert gap_detection(ProposedMapping(), golden).score == pytest.approx(1.0)


# ── confidence_calibration ──────────────────────────────────────────────────────────────
def test_confidence_calibration_positive_margin() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT", confidence=0.9),
            Proposal(
                concept="partner number", table="VICTOR_PARTNER", column="KD_NR", confidence=0.3
            ),
        ]
    )
    result = confidence_calibration(proposed, golden)
    assert result.score == pytest.approx(0.6)  # 0.9 correct - 0.3 wrong
    assert "margin=0.60" in result.details


def test_confidence_calibration_no_wrong_reports_it() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT", confidence=0.8)
        ]
    )
    result = confidence_calibration(proposed, golden)
    assert result.score == pytest.approx(0.8)
    assert "no wrong proposals" in result.details


def test_score_mapping_runs_all_three() -> None:
    results = score_mapping(ProposedMapping(), _golden())
    assert {r.name for r in results} == set(MAPPING_SCORERS)


# ── the real messy_insurance golden set (D1) ──────────────────────────────────────────────
def test_real_golden_loads_and_carries_the_traps() -> None:
    golden = load_golden_mapping(GOLDEN_PATH)
    # Synonym trap: an ambiguous concept with >= 2 candidates.
    assert any(len(a.candidates) >= 2 for a in golden.ambiguous)
    # Statistics trap: partner number is golden to PARTN_NR, NOT the flawless PARTN_GUID.
    partner_bk = next(m for m in golden.mappings if m.concept == "partner number")
    assert partner_bk.source_column == "PARTN_NR"
    assert all(m.source_column != "PARTN_GUID" for m in golden.mappings if m.kind == "business_key")
    # False-friend trap present.
    assert any(f.column == "KD_NR" for f in golden.false_friends)
    # Genuine gap: >= 2 no-source concepts.
    assert len(golden.gaps) >= 2


def test_concepts_for_prototype_hides_answers_and_mixes_gaps() -> None:
    golden = load_golden_mapping(GOLDEN_PATH)
    refs = concepts_for_prototype(golden)
    concept_labels = [r.concept for r in refs]
    # Every mappable, ambiguous, and gap concept appears exactly once, no duplicates.
    assert len(concept_labels) == len(set(concept_labels))
    for m in golden.mappings:
        assert m.concept in concept_labels
    for g in golden.gaps:
        assert g.concept in concept_labels
    # A ConceptRef exposes only concept/entity/kind — never the source column (no leak).
    assert all(not hasattr(r, "source_column") for r in refs)
    # Gaps are not all clustered at the tail (sorted by entity/concept): at least one gap
    # concept is followed by a non-gap concept.
    gap_set = {g.concept for g in golden.gaps}
    positions = [i for i, label in enumerate(concept_labels) if label in gap_set]
    assert positions and min(positions) < len(concept_labels) - len(gap_set) or len(gap_set) == 1


def test_load_golden_mapping_rejects_non_mapping(tmp_path) -> None:
    bad = tmp_path / "golden_mapping.yml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a mapping"):
        load_golden_mapping(bad)


def test_load_golden_mapping_empty_is_empty() -> None:
    # An all-comments/empty document loads as an empty golden set (parity with the loaders).
    golden = GoldenMapping.model_validate({})
    assert not golden.mappings and not golden.gaps
    assert math.isclose(mapping_accuracy(ProposedMapping(), golden).score, 1.0)
