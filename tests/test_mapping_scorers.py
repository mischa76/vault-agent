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
from eval.run import vacuous_scorers
from eval.scorers import (
    MAPPING_SCORERS,
    VACUOUS_PREFIX,
    confidence_calibration,
    false_friend_hits,
    gap_detection,
    mapping_accuracy,
    mapping_coverage,
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


def test_confidence_calibration_no_wrong_is_perfect_margin() -> None:
    # WP9.2: with no wrong proposals to separate from, the margin is 1.0 by definition
    # (perfect separation), not the mean confidence.
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT", confidence=0.8)
        ]
    )
    result = confidence_calibration(proposed, golden)
    assert result.score == pytest.approx(1.0)
    assert "no wrong proposals" in result.details


# ── WP9.2: golden-universe restriction (the bank live-run artefact) ───────────────────────
def _bank_golden() -> GoldenMapping:
    """Six exact-match golden concepts (the bank case; no gaps/ambiguous)."""
    cols = [
        ("national customer ID", "customer", "national_customer_id"),
        ("account number", "account", "account_number"),
        ("customer name", "customer", "customer_name"),
        ("date of birth", "customer", "date_of_birth"),
        ("balance", "account", "balance"),
        ("status", "account", "status"),
    ]
    return GoldenMapping(
        mappings=[
            GoldenMappingEntry(concept=c, source_table=t, source_column=col) for c, t, col in cols
        ]
    )


def _bank_proposed() -> ProposedMapping:
    """Nine confident proposals: the six golden concepts (correct) + three the generated
    model added that the golden set does not cover (effective_from/effective_to/txn amount)."""
    golden = [
        ("national customer ID", "customer", "national_customer_id"),
        ("account number", "account", "account_number"),
        ("customer name", "customer", "customer_name"),
        ("date of birth", "customer", "date_of_birth"),
        ("balance", "account", "balance"),
        ("status", "account", "status"),
    ]
    extra = [
        ("effective from", "account_customer", "effective_from"),
        ("effective to", "account_customer", "effective_to"),
        ("transaction amount", "transaction", "amount"),
    ]
    return ProposedMapping(
        proposals=[
            Proposal(concept=c, table=t, column=col, confidence=0.97)
            for c, t, col in golden + extra
        ]
    )


def test_mapping_accuracy_ignores_out_of_universe_proposals() -> None:
    result = mapping_accuracy(_bank_proposed(), _bank_golden())
    assert result.score == pytest.approx(1.0)  # 6/6 scored correct; the 3 extras don't count
    assert "precision=1.00 6/6" in result.details
    assert "3 proposals outside the golden universe, unscored" in result.details


def test_confidence_calibration_ignores_out_of_universe_proposals() -> None:
    # The 3 confident out-of-universe proposals used to masquerade as "wrong" and collapse
    # the margin; now they are not scored, so the margin is a clean 1.0 (n=6 correct, n=0 wrong).
    result = confidence_calibration(_bank_proposed(), _bank_golden())
    assert result.score == pytest.approx(1.0)
    assert "n=6" in result.details and "no wrong proposals" in result.details


def test_score_mapping_runs_all_three() -> None:
    results = score_mapping(ProposedMapping(), _golden())
    assert {r.name for r in results} == set(MAPPING_SCORERS)


# ── WP14: column-mode scorers (scale cases) ───────────────────────────────────────────────
def test_mapping_coverage_full_is_one() -> None:
    golden = _golden()  # mappable: partner number, city, customer reference (ambiguous)
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="partner number", table="victor_partner", column="partn_nr"),
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT"),
            Proposal(
                concept="customer reference", table="CRM_ACCOUNT", column="ExternalCustomerNo"
            ),
        ]
    )
    result = mapping_coverage(proposed, golden)
    assert result.score == pytest.approx(1.0)  # 3/3 golden pairs bound
    assert "3/3" in result.details


def test_mapping_coverage_partial_and_reports_missed() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT"),
            # the ambiguous second candidate covers "customer reference" ...
            Proposal(
                concept="customer reference", table="CRM_ACCOUNT", column="ExternalCustomerNo"
            ),
            # ... but "partner number" (PARTN_NR) is never bound
        ]
    )
    result = mapping_coverage(proposed, golden)
    assert result.score == pytest.approx(2 / 3)
    assert "missed" in result.details and "PARTN_NR" in result.details


def test_mapping_coverage_zero_and_out_of_golden_reported() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[Proposal(concept="something", table="OTHER_TBL", column="OTHER_COL")]
    )
    result = mapping_coverage(proposed, golden)
    assert result.score == pytest.approx(0.0)
    # the stray binding is reported, never penalises the coverage denominator
    assert "1 proposal(s) outside the golden column set" in result.details


def test_mapping_coverage_statistics_trap_guid_pair_misses() -> None:
    # Binding the shadow GUID is a different (table, column) pair than the real key → not covered.
    golden = GoldenMapping(
        mappings=[
            GoldenMappingEntry(
                concept="partner number",
                source_table="VICTOR_PARTNER",
                source_column="PARTN_NR",
                kind="business_key",
            )
        ]
    )
    proposed = ProposedMapping(
        proposals=[Proposal(concept="partner number", table="VICTOR_PARTNER", column="PARTN_GUID")]
    )
    assert mapping_coverage(proposed, golden).score == pytest.approx(0.0)


def test_mapping_coverage_is_blind_to_concept_and_entity() -> None:
    # Pair match only: a proposal with an unrelated concept/entity but the right column still
    # covers the golden entry — the property that makes column mode honest at scale.
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(
                concept="totally unrelated label",
                entity="not_partner",
                table="VICTOR_PARTNER",
                column="KD_ORT",
            )
        ]
    )
    result = mapping_coverage(proposed, golden)
    assert result.score == pytest.approx(1 / 3)  # "city" covered despite the concept mismatch


def test_mapping_coverage_vacuous_without_mappable_entries() -> None:
    assert mapping_coverage(ProposedMapping(), GoldenMapping()).score == pytest.approx(1.0)


def test_false_friend_hits_clean_is_one() -> None:
    golden = _golden()  # KD_NR is the watched false friend
    proposed = ProposedMapping(
        proposals=[Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT")]
    )
    result = false_friend_hits(proposed, golden)
    assert result.score == pytest.approx(1.0)
    assert "watched" in result.details


def test_false_friend_hits_binding_a_friend_is_zero_and_named() -> None:
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[Proposal(concept="partner number", table="VICTOR_PARTNER", column="KD_NR")]
    )
    result = false_friend_hits(proposed, golden)
    assert result.score == pytest.approx(0.0)
    assert "FALSE-FRIEND HIT" in result.details and "KD_NR" in result.details


def test_score_mapping_column_mode_swaps_the_scorers() -> None:
    results = score_mapping(ProposedMapping(), _golden(), mode="column")
    assert {r.name for r in results} == {
        "mapping_coverage",
        "false_friend_hits",
        "gap_detection",
    }


def test_gap_detection_reported_only_marks_details_non_gateable() -> None:
    golden = _golden()
    proposed = ProposedMapping(gaps=["Schadenquote je Partner"])
    result = gap_detection(proposed, golden, reported_only=True)
    assert result.score == pytest.approx(1.0)  # score unchanged from the un-prefixed form
    assert result.details.startswith("concept-coupled — reported only in column mode;")


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


# ── WP18: one vacuity convention across the mapping family ──────────────────────────────
def test_every_mapping_scorer_marks_a_vacuous_verdict_the_same_way() -> None:
    """Nothing to check ⇒ score 1.0 and details starting with the shared prefix.

    The prefix is the only thing ``eval.run.vacuous_scorers`` keys on — it both marks the
    console summary and refuses a gate on a scorer that never had anything to score. Before
    WP18 four of these branches were unmarked and ``confidence_calibration`` even scored the
    case 0.0, the opposite polarity."""
    empty = GoldenMapping()
    verdicts = [
        mapping_accuracy(ProposedMapping(), empty),
        mapping_coverage(ProposedMapping(), empty),
        false_friend_hits(ProposedMapping(), empty),
        gap_detection(ProposedMapping(), empty),
        confidence_calibration(ProposedMapping(), empty),
    ]
    for verdict in verdicts:
        assert verdict.score == pytest.approx(1.0), verdict.name
        assert verdict.details.startswith(VACUOUS_PREFIX), verdict.name
    # and the runner recognises every one of them as vacuous across repeats
    assert vacuous_scorers([verdicts, verdicts]) == sorted(v.name for v in verdicts)


def test_gap_detection_column_mode_keeps_the_vacuous_marker_first() -> None:
    # Composition order matters: the reported-only note must not shadow the startswith key.
    verdict = gap_detection(ProposedMapping(), GoldenMapping(), reported_only=True)
    assert verdict.details.startswith(VACUOUS_PREFIX)
    assert "reported only in column mode" in verdict.details


def test_false_friend_hits_with_declared_friends_is_not_vacuous() -> None:
    # A real clean bill of health stays distinguishable from "nothing was watched".
    verdict = false_friend_hits(ProposedMapping(), _golden())
    assert verdict.score == pytest.approx(1.0)
    assert not verdict.details.startswith(VACUOUS_PREFIX)
    assert "watched" in verdict.details


def test_confidence_calibration_vacuous_only_without_any_scored_proposal() -> None:
    # Polarity regression guard: a real margin is untouched by the vacuity fix.
    golden = _golden()
    proposed = ProposedMapping(
        proposals=[
            Proposal(concept="city", table="VICTOR_PARTNER", column="KD_ORT", confidence=0.9),
            Proposal(
                concept="partner number", table="VICTOR_PARTNER", column="KD_NR", confidence=0.3
            ),
        ]
    )
    verdict = confidence_calibration(proposed, golden)
    assert verdict.score == pytest.approx(0.6)
    assert not verdict.details.startswith(VACUOUS_PREFIX)
