"""Pinned-score tests for the deterministic scorers (WP6 layer 2). No API key."""
import pytest

from eval.datasets import (
    DATASETS_ROOT,
    EvalCase,
    Expectations,
    GoldenHub,
    GoldenLink,
    GoldenModel,
    GoldenSatellite,
    load_eval_case,
)
from eval.scorers import (
    SCORERS,
    construct_f1,
    driving_key_accuracy,
    pipeline_health,
    score_state,
    validation_gate,
)
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    Satellite,
    ValidationIssue,
    VaultAgentState,
)


def _case(golden: GoldenModel, expectations: Expectations | None = None) -> EvalCase:
    return EvalCase(
        name="synthetic",
        input_document="unused.md",
        golden=golden,
        expectations=expectations or Expectations(),
    )


def _hub(name: str, business_key: str) -> Hub:
    return Hub(name=name, business_key=business_key, source_entity=name, description="d")


def _link(name: str, hubs: list[str], driving_key: list[str] | None = None) -> Link:
    return Link(name=name, connected_hubs=hubs, description="d", driving_key=driving_key or [])


def _sat(
    name: str,
    parent: str,
    sat_type: str = "standard",
    attributes: list[str] | None = None,
) -> Satellite:
    return Satellite(
        name=name,
        parent=parent,
        description="d",
        sat_type=sat_type,  # type: ignore[arg-type]
        attributes=attributes or [],
    )


# --- construct_f1 -------------------------------------------------------------------


def test_construct_f1_perfect_match_is_1() -> None:
    golden = GoldenModel(
        hubs=[GoldenHub(name="hub_customer", business_key="national customer ID")],
        links=[GoldenLink(name="link_a_c", connected_hubs=["hub_account", "hub_customer"])],
        satellites=[
            GoldenSatellite(name="sat_c", parent="hub_customer", sat_type="standard")
        ],
    )
    state = VaultAgentState(
        dv_model=DVModel(
            # Structural matching: generated side uses normalised identifiers.
            hubs=[_hub("HUB_CUSTOMER", "NATIONAL_CUSTOMER_ID")],
            links=[_link("link_a_c", ["hub_customer", "hub_account"])],  # set, not order
            satellites=[_sat("sat_c", "hub_customer")],
        )
    )
    result = construct_f1(state, _case(golden))
    assert result.score == 1.0


def test_construct_f1_two_of_three_hubs_pins_8_9ths() -> None:
    golden = GoldenModel(
        hubs=[
            GoldenHub(name="hub_a", business_key="a"),
            GoldenHub(name="hub_b", business_key="b"),
            GoldenHub(name="hub_c", business_key="c"),
        ],
        links=[GoldenLink(name="link_ab", connected_hubs=["hub_a", "hub_b"])],
    )
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[
                _hub("hub_a", "a"),
                _hub("hub_b", "b"),
                _hub("hub_c", "wrong key"),  # name matches, business key does not
            ],
            links=[_link("link_ab", ["hub_a", "hub_b"])],
        )
    )
    result = construct_f1(state, _case(golden))
    # hubs: P=R=2/3 -> F1=2/3; links: 1.0; satellites: vacuous 1.0; mean = 8/9.
    assert result.score == pytest.approx(8 / 9)
    assert "hubs: 2/3 golden matched, 3 generated" in result.details


def test_construct_f1_zero_when_golden_expected_but_nothing_generated() -> None:
    golden = GoldenModel(hubs=[GoldenHub(name="hub_a", business_key="a")])
    result = construct_f1(VaultAgentState(), _case(golden))
    # hubs 0.0; links and satellites vacuous 1.0.
    assert result.score == pytest.approx(2 / 3)


def test_construct_f1_penalises_ungolden_extras() -> None:
    golden = GoldenModel()  # nothing expected
    state = VaultAgentState(dv_model=DVModel(hubs=[_hub("hub_a", "a")]))
    result = construct_f1(state, _case(golden))
    assert result.score == pytest.approx(2 / 3)  # hubs F1 0.0, links/sats vacuous


def test_construct_f1_link_requires_same_hub_set() -> None:
    golden = GoldenModel(
        links=[GoldenLink(name="link_ab", connected_hubs=["hub_a", "hub_b"])]
    )
    state = VaultAgentState(
        dv_model=DVModel(links=[_link("link_ab", ["hub_a", "hub_x"])])
    )
    result = construct_f1(state, _case(golden))
    assert result.score == pytest.approx(2 / 3)  # links F1 0.0


def test_construct_f1_satellite_requires_parent_and_type() -> None:
    golden = GoldenModel(
        satellites=[GoldenSatellite(name="sat_a", parent="hub_a", sat_type="effectivity")]
    )
    state = VaultAgentState(
        dv_model=DVModel(satellites=[_sat("sat_a", "hub_a", sat_type="standard")])
    )
    result = construct_f1(state, _case(golden))
    assert result.score == pytest.approx(2 / 3)  # satellites F1 0.0


def test_construct_f1_optional_golden_attributes_compared_as_normalised_sets() -> None:
    golden = GoldenModel(
        satellites=[
            GoldenSatellite(
                name="sat_c",
                parent="hub_c",
                attributes=["customer name", "date of birth"],
            )
        ]
    )
    matching = VaultAgentState(
        dv_model=DVModel(
            satellites=[_sat("sat_c", "hub_c", attributes=["DATE_OF_BIRTH", "CUSTOMER_NAME"])]
        )
    )
    diverging = VaultAgentState(
        dv_model=DVModel(satellites=[_sat("sat_c", "hub_c", attributes=["CUSTOMER_NAME"])])
    )
    assert construct_f1(matching, _case(golden)).score == 1.0
    assert construct_f1(diverging, _case(golden)).score == pytest.approx(2 / 3)


# --- driving_key_accuracy -----------------------------------------------------------


def test_driving_key_accuracy_no_golden_keys_is_1() -> None:
    golden = GoldenModel(links=[GoldenLink(name="l", connected_hubs=["a", "b"])])
    result = driving_key_accuracy(VaultAgentState(), _case(golden))
    assert result.score == 1.0
    assert "no golden driving keys" in result.details


def test_driving_key_accuracy_half_correct_pins_0_5() -> None:
    golden = GoldenModel(
        links=[
            GoldenLink(
                name="link_ac", connected_hubs=["hub_a", "hub_c"], driving_key=["hub_a"]
            ),
            GoldenLink(
                name="link_bc", connected_hubs=["hub_b", "hub_c"], driving_key=["hub_b"]
            ),
        ]
    )
    state = VaultAgentState(
        dv_model=DVModel(
            links=[
                _link("LINK_AC", ["hub_a", "hub_c"], driving_key=["HUB_A"]),  # normalised
                _link("link_bc", ["hub_b", "hub_c"], driving_key=["hub_c"]),  # wrong side
            ]
        )
    )
    result = driving_key_accuracy(state, _case(golden))
    assert result.score == 0.5
    assert "link_bc" in result.details


def test_driving_key_accuracy_missing_counterpart_is_a_miss() -> None:
    golden = GoldenModel(
        links=[GoldenLink(name="link_ac", connected_hubs=["a", "c"], driving_key=["a"])]
    )
    result = driving_key_accuracy(VaultAgentState(), _case(golden))
    assert result.score == 0.0
    assert "no generated counterpart" in result.details


# --- link resolution: grain, not name -----------------------------------------------
# The modeller names links freely: link_policy_insured_person and link_insured_person_policy
# are one construct. Observed live on health_insurance (2026-07-27), where name-keyed
# matching scored a DV-correct model as links F1=0.29 / driving_key 0.00.


def test_link_matches_despite_reversed_name_component_order() -> None:
    golden = GoldenModel(
        links=[
            GoldenLink(
                name="link_insured_person_policy",
                connected_hubs=["hub_insured_person", "hub_policy"],
                driving_key=["hub_policy"],
            )
        ]
    )
    state = VaultAgentState(
        dv_model=DVModel(
            links=[
                _link(
                    "link_policy_insured_person",
                    ["hub_policy", "hub_insured_person"],
                    driving_key=["hub_policy"],
                )
            ]
        )
    )
    case = _case(golden)
    assert driving_key_accuracy(state, case).score == 1.0
    # hubs/satellites vacuous 1.0, links 1.0
    assert construct_f1(state, case).score == pytest.approx(1.0)


def test_link_grain_distinguishes_self_reference_from_single_participation() -> None:
    """A hub participating twice is a different grain than participating once."""
    golden = GoldenModel(
        links=[GoldenLink(name="link_transfer", connected_hubs=["hub_account", "hub_account"])]
    )
    state = VaultAgentState(dv_model=DVModel(links=[_link("link_transfer", ["hub_account"])]))
    assert construct_f1(state, _case(golden)).score == pytest.approx(2 / 3)  # links F1 0.0


def test_ambiguous_grain_is_disambiguated_by_name() -> None:
    """Two links over the same hubs (W_LINK_REDUNDANT_GRAIN territory): the name breaks the tie."""
    golden = GoldenModel(
        links=[
            GoldenLink(
                name="link_b_a", connected_hubs=["hub_a", "hub_b"], driving_key=["hub_b"]
            )
        ]
    )
    state = VaultAgentState(
        dv_model=DVModel(
            links=[
                _link("link_a_b", ["hub_a", "hub_b"], driving_key=["hub_a"]),  # wrong side
                _link("link_b_a", ["hub_b", "hub_a"], driving_key=["hub_b"]),  # named match
            ]
        )
    )
    assert driving_key_accuracy(state, _case(golden)).score == 1.0


def test_ambiguous_grain_without_a_name_match_stays_unmatched() -> None:
    """Never guess between equally-plausible candidates — an unresolvable tie is a miss."""
    golden = GoldenModel(
        links=[
            GoldenLink(
                name="link_totally_different",
                connected_hubs=["hub_a", "hub_b"],
                driving_key=["hub_a"],
            )
        ]
    )
    state = VaultAgentState(
        dv_model=DVModel(
            links=[
                _link("link_a_b", ["hub_a", "hub_b"], driving_key=["hub_a"]),
                _link("link_b_a", ["hub_b", "hub_a"], driving_key=["hub_a"]),
            ]
        )
    )
    result = driving_key_accuracy(state, _case(golden))
    assert result.score == 0.0
    assert "no generated counterpart" in result.details


# --- validation_gate ----------------------------------------------------------------


def _issue(severity: str, code: str) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        construct="model",
        message="m",
    )


def test_validation_gate_pass_within_tolerance() -> None:
    state = VaultAgentState()
    state.validation_report.passed = True
    state.validation_report.issues = [_issue("warning", "W_X"), _issue("warning", "W_Y")]
    case = _case(
        GoldenModel(),
        Expectations(validation_passed=True, max_validation_warnings=2),
    )
    assert validation_gate(state, case).score == 1.0


def test_validation_gate_fails_on_outcome_mismatch() -> None:
    state = VaultAgentState()  # passed=False by default
    case = _case(GoldenModel(), Expectations(validation_passed=True))
    result = validation_gate(state, case)
    assert result.score == 0.0
    assert "passed=False" in result.details


def test_validation_gate_fails_when_warnings_exceed_tolerance() -> None:
    state = VaultAgentState()
    state.validation_report.passed = True
    state.validation_report.issues = [_issue("warning", f"W_{i}") for i in range(3)]
    case = _case(
        GoldenModel(),
        Expectations(validation_passed=True, max_validation_warnings=2),
    )
    result = validation_gate(state, case)
    assert result.score == 0.0
    assert "3 warning(s) exceed the tolerance of 2" in result.details


def test_validation_gate_no_tolerance_means_no_warning_check() -> None:
    state = VaultAgentState()
    state.validation_report.passed = True
    state.validation_report.issues = [_issue("warning", f"W_{i}") for i in range(50)]
    case = _case(GoldenModel(), Expectations(validation_passed=True))
    assert validation_gate(state, case).score == 1.0


# --- pipeline_health ----------------------------------------------------------------


def test_pipeline_health_clean_and_advisory_only_is_1(empty_state: VaultAgentState) -> None:
    assert pipeline_health(empty_state, _case(GoldenModel())).score == 1.0
    empty_state.flag("modeler", "dropped a record", severity="advisory")
    assert pipeline_health(empty_state, _case(GoldenModel())).score == 1.0


def test_pipeline_health_error_flag_is_0_with_details(empty_state: VaultAgentState) -> None:
    empty_state.flag(
        "code_generator", "boom", severity="error", kind="generation_gap", asset="sat_x"
    )
    result = pipeline_health(empty_state, _case(GoldenModel()))
    assert result.score == 0.0
    assert "code_generator: generation_gap (sat_x)" in result.details


# --- score_state / bank end-to-end pin ------------------------------------------------


def test_score_state_applies_all_scorers() -> None:
    results = score_state(VaultAgentState(), _case(GoldenModel()))
    assert [result.name for result in results] == list(SCORERS)


def test_bank_case_scores_perfectly_against_the_durchstich_model() -> None:
    """The shipped bank golden is satisfied exactly by the demo's fixed DV model."""
    case = load_eval_case(DATASETS_ROOT / "bank" / "dataset.yml")
    state = VaultAgentState(
        dv_model=DVModel(
            hubs=[
                _hub("hub_customer", "national customer ID"),
                _hub("hub_account", "account number"),
            ],
            links=[
                _link(
                    "link_account_customer",
                    ["hub_account", "hub_customer"],
                    driving_key=["hub_account"],
                )
            ],
            satellites=[
                _sat("sat_customer_details", "hub_customer"),
                _sat("sat_account_details", "hub_account"),
                _sat("sat_account_customer_eff", "link_account_customer", "effectivity"),
            ],
        )
    )
    state.validation_report.passed = True
    scores = {result.name: result.score for result in score_state(state, case)}
    assert scores == {
        "construct_f1": 1.0,
        "driving_key_accuracy": 1.0,
        "validation_gate": 1.0,
        "pipeline_health": 1.0,
    }
