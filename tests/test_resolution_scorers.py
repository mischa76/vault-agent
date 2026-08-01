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
from vault_agent.state import concept_key

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
    """Build proposals keyed the way the PIPELINE keys them, from the golden's own coordinates.

    The kwargs stay the golden's readable labels (``partner=``, ``kontakt=``) so each test still
    says what it is about. Deliberate update, WP29.1: these tests were written for the spike,
    which drove the resolver directly and used those labels as the key. The product emits
    ``entity::field`` (``concept_key``), and after WP29 §2.2 collapsed the eval types into the
    product's, a scorer keyed on anything else measures a shape nothing produces."""
    by_label = {e.concept: e for e in _golden().resolutions}
    return ResolutionResult(
        proposals=[
            ProposedResolution(
                concept=concept_key(by_label[c].source_key, by_label[c].source_table),
                resolution=r,
                confidence=0.9,
            )
            for c, r in answers.items()
        ]
    )


def _key(label: str) -> str:
    """The pipeline key for a golden concept, by its readable label (WP29.1)."""
    entry = {e.concept: e for e in _golden().resolutions}[label]
    return concept_key(entry.source_key, entry.source_table)


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
    assert f'{_key("kontakt")} -> hub_customer (golden: NEW)' in result.details


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
        ProposedResolution(concept=_key("partner"), resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept=_key("kontakt"), resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept=_key("crm_kunde"), resolution="same_as_candidate",
                           same_as="hub_customer", confidence=0.9),
    ])

    assert resolution_accuracy(_golden(), dangerous).score == pytest.approx(2 / 3)
    assert false_merge_rate(_golden(), dangerous).score == 0.0


def test_a_same_as_pointing_at_the_wrong_construct_is_not_accurate() -> None:
    result = ResolutionResult(proposals=[
        ProposedResolution(concept=_key("crm_kunde"), resolution="same_as_candidate",
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
        ProposedResolution(concept=_key("partner"), resolution="hub_customer"),
        ProposedResolution(concept=_key("kontakt"), resolution="NEW"),
        ProposedResolution(concept=_key("crm_kunde"), resolution="same_as_candidate",
                           same_as="hub_customer"),
    ])

    assert new_hub_detection(_golden(), result).score == 1.0


# ── calibration ───────────────────────────────────────────────────────────────────────────
def test_calibration_measures_the_margin_between_right_and_wrong() -> None:
    result = ResolutionResult(proposals=[
        ProposedResolution(concept=_key("partner"), resolution="hub_customer", confidence=0.9),
        ProposedResolution(concept=_key("kontakt"), resolution="hub_customer", confidence=0.3),
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


# ── WP29: the DERIVED category (spec §2.3, from a measured failure) ────────────────────────
def _hubs():  # type: ignore[no-untyped-def]
    from vault_agent.state import Hub

    return [
        Hub(name="hub_customer", business_key="national customer ID",
            source_entity="customer", description=""),
        Hub(name="hub_account", business_key="account number", source_entity="account",
            description=""),
    ]


def _tables(**cols: dict[str, str | None]):  # type: ignore[no-untyped-def]
    from vault_agent.state import SourceColumn, SourceTable

    return [
        SourceTable(table=name, columns=[
            SourceColumn(name=c, type="varchar", comment=comment)
            for c, comment in spec.items()
        ])
        for name, spec in cols.items()
    ]


def test_category_exact_key_when_the_concept_key_is_the_business_key() -> None:
    from vault_agent.rules.dv2_rules import resolution_category

    assert resolution_category(
        "national_customer_id", "hub_customer", _hubs(), [], []
    ) == "exact_key"


def test_category_key_overlap_when_a_cross_reference_carries_both_keys() -> None:
    """The same-as shape: asserted equivalence, not identity."""
    from vault_agent.rules.dv2_rules import resolution_category

    tables = _tables(crm_xref={"crm_guid": None, "national_customer_id": None})

    assert resolution_category(
        "crm_guid", "same_as_candidate", _hubs(), tables, []
    ) == "key_overlap"


def test_category_comment_grounded_when_a_comment_names_the_business_key() -> None:
    from vault_agent.rules.dv2_rules import resolution_category

    tables = _tables(vic_partner={"partn_nr": "Nationale Kundennummer / national customer ID"})

    assert resolution_category(
        "partn_nr", "hub_customer", _hubs(), tables, []
    ) == "comment_grounded"


def test_category_falls_back_to_semantic() -> None:
    from vault_agent.rules.dv2_rules import resolution_category

    tables = _tables(t={"alt_nr": None})

    assert resolution_category("alt_nr", "NEW", _hubs(), tables, []) == "semantic"


def test_the_models_own_category_claim_is_ignored() -> None:
    """The measured reason this helper exists: the resolver reported `semantic` for every
    case, including exact-key ones where its answer was right (spike memo §3.3)."""
    from vault_agent.rules.dv2_rules import resolution_category
    from vault_agent.state import ResolutionProposal

    claimed = ResolutionProposal(concept="konto", resolution="hub_account",
                                 category="semantic", confidence=0.97)
    derived = resolution_category("account_number", claimed.resolution, _hubs(), [], [])

    assert claimed.category == "semantic"  # what the model said
    assert derived == "exact_key"          # what is actually true


# --- WP29.1: the scorers must match the keys the PIPELINE emits --------------------------
#
# The golden keys concepts by a bare label plus (source_table, source_key); the pipeline emits
# `entity::field`. Matching on the label meant nothing ever matched — and false_merge_rate's
# unmatched branch appended to `offenders`, so every CORRECT merge scored as a false one and
# the gate would have read 0.000 in every repeat. Fourth appearance of the class
# `.claude/rules/eval.md` puts first: score structure, not free-form names.

def _pipeline(concept_key_str: str, resolution: str, **kw: object) -> ProposedResolution:
    return ProposedResolution(concept=concept_key_str, resolution=resolution, **kw)  # type: ignore[arg-type]


def test_a_correct_merge_on_pipeline_keys_scores_1() -> None:
    """`vic_partner::partn_nr` IS the golden's `partner` — matched by (table, key)."""
    result = ResolutionResult(proposals=[_pipeline("vic_partner::partn_nr", "hub_customer")])

    scored = false_merge_rate(_golden(), result)

    assert scored.score == 1.0, scored.details


def test_a_merge_onto_the_wrong_hub_still_scores_0() -> None:
    """The structural match must not soften the property it exists to measure."""
    result = ResolutionResult(proposals=[_pipeline("vic_partner::partn_nr", "hub_account")])

    scored = false_merge_rate(_golden(), result)

    assert scored.score == 0.0
    assert "FALSE MERGE" in scored.details


def test_a_merge_of_a_concept_the_golden_does_not_carry_is_out_of_universe() -> None:
    """WP14 semantics: unmatched is OUT OF UNIVERSE, not evidence of a false merge.

    The golden is deliberately narrow — seven traps, not every concept the pipeline will
    propose. Counting an unmatched proposal as an offender turns the golden's own narrowness
    into a product defect."""
    result = ResolutionResult(proposals=[
        _pipeline("vic_partner::partn_nr", "hub_customer"),   # matched, correct
        _pipeline("some_other_table::some_key", "hub_account"),  # not in the golden at all
    ])

    scored = false_merge_rate(_golden(), result)

    assert scored.score == 1.0, scored.details
    assert "unscored" in scored.details or "outside" in scored.details, scored.details


def test_accuracy_matches_on_pipeline_keys_too() -> None:
    """All four scorers key the same way, or they disagree about what was answered."""
    result = ResolutionResult(proposals=[
        _pipeline("vic_partner::partn_nr", "hub_customer"),
        _pipeline("vic_kontakt::kontakt_id", "NEW"),
    ])

    scored = resolution_accuracy(_golden(), result)

    assert scored.score > 0.0, scored.details


def test_new_hub_detection_matches_on_pipeline_keys() -> None:
    result = ResolutionResult(proposals=[_pipeline("vic_kontakt::kontakt_id", "NEW")])

    scored = new_hub_detection(_golden(), result)

    assert scored.score > 0.0, scored.details


def test_calibration_matches_on_pipeline_keys() -> None:
    result = ResolutionResult(proposals=[
        _pipeline("vic_partner::partn_nr", "hub_customer", confidence=0.9),
        _pipeline("vic_kontakt::kontakt_id", "hub_customer", confidence=0.2),  # wrong
    ])

    scored = resolution_calibration(_golden(), result)

    # Not merely >0: with nothing matched, both sides are empty and the scorer returns a
    # VACUOUS 1.0. The point is that it SAW the two proposals and separated them.
    assert VACUOUS_PREFIX not in scored.details, scored.details
    assert scored.score > 0.0, scored.details
