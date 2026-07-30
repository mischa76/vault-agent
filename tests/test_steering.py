"""Keyless tests for the steering registry, the ablation seam, and backstop telemetry (WP16).

The registry exists to make model-compensation *measurable*: every steering line has a stable
id, the backstop behind it (where one exists) fires observably, and one line can be dropped
from the prompt for an ablation arm. Acceptance #1 is byte-identity: with no exclusions and no
recorder, nothing about the pipeline changes.
"""
import dataclasses
from pathlib import Path

import pytest

from vault_agent import llm
from vault_agent.rules import dv2_rules
from vault_agent.rules.dv2_rules import (
    DV_MODELING_RULES,
    SteeringRule,
    active_modeling_rules,
    excluded_rules,
    set_excluded_rules,
)

_RULES_FIXTURE = Path(__file__).parent / "fixtures" / "steering" / "modeler_rules_pre_wp16.txt"


def _render_rules() -> str:
    """Exactly how the modeler renders the rules block into its system prompt."""
    return "\n".join(f"- {rule.text}" for rule in active_modeling_rules())


@pytest.fixture(autouse=True)
def _no_exclusions_leak():
    yield
    set_excluded_rules(None)


# --- Registry -----------------------------------------------------------------------------


def test_rule_ids_are_unique_and_snake_case() -> None:
    ids = [rule.id for rule in DV_MODELING_RULES]
    assert len(ids) == len(set(ids))
    assert all(rule_id and rule_id.replace("_", "").isalnum() for rule_id in ids)


def test_rendered_rules_are_byte_identical_to_pre_wp16() -> None:
    # Acceptance #1: turning the list[str] into a registry must not move a single character of
    # the prompt — the fixture was generated from the pre-WP16 constant.
    #
    # It is now also the standing pin on the modeler prompt: a rule may only be added or
    # changed together with this fixture, in the same commit, named in the commit body. A
    # silent update is exactly what the pin exists to prevent. Deliberate additions so far:
    # WP20 `construct_naming` (2026-07-28) added; WP23 added
    # `no_source_table_on_multi_source_hub` and WP28 DELETED it again the same day, after
    # ADR-0011 blessed the shape it argued against (and after it measured 0/3 effective);
    # WP31 `attribute_one_satellite` (2026-07-30) added, for the E_SAT_ATTR_OVERLAP class
    # ADR-0012 keeps as an error.
    # The pre-WP16 block remains a byte-identical prefix — a deletion of a rule ADDED
    # after WP16 cannot disturb it, which is exactly why the pin is written that way, and
    # each addition above was verified to preserve the prefix while regenerating.
    assert _render_rules() + "\n" == _RULES_FIXTURE.read_text(encoding="utf-8")


def test_modeler_system_prompt_carries_the_rendered_rules() -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    from vault_agent.state import VaultAgentState

    prompt = Dv2ModelerAgent()._build_system_prompt(VaultAgentState())
    assert _render_rules() in prompt


def test_backstopped_rules_name_a_real_backstop() -> None:
    # The ledger's value rests on this link: a rule's fire count is only meaningful if the
    # backstop id it names is the one the code emits.
    linked = {rule.backstop for rule in DV_MODELING_RULES if rule.backstop}
    assert linked == {"attributes_without_cdk", "effsat_two_attributes"}


def test_every_rule_records_its_origin() -> None:
    assert all(rule.origin for rule in DV_MODELING_RULES)


# --- Ablation seam ------------------------------------------------------------------------


def test_exclusion_drops_exactly_the_named_line() -> None:
    baseline = _render_rules()
    dropped = next(rule for rule in DV_MODELING_RULES if rule.id == "cdk_not_payload")

    set_excluded_rules(["cdk_not_payload"])

    assert excluded_rules() == frozenset({"cdk_not_payload"})
    ablated = _render_rules()
    assert f"- {dropped.text}" not in ablated
    assert len(ablated.splitlines()) == len(baseline.splitlines()) - len(
        dropped.text.splitlines()
    )
    for rule in DV_MODELING_RULES:
        if rule.id != "cdk_not_payload":
            assert rule.text in ablated


def test_clearing_exclusions_restores_identity() -> None:
    baseline = _render_rules()
    set_excluded_rules(["unit_of_work"])
    assert _render_rules() != baseline

    set_excluded_rules(None)

    assert _render_rules() == baseline
    assert excluded_rules() == frozenset()


def test_unknown_rule_id_raises_attributably() -> None:
    # A silently ignored typo would report a rule as "safe to delete" while it was still in
    # the prompt — the one failure mode that must not be quiet.
    with pytest.raises(ValueError, match="unknown steering rule id"):
        set_excluded_rules(["cdk_not_payload", "no_such_rule"])
    assert excluded_rules() == frozenset()  # nothing applied on the failing call


def test_production_code_never_excludes_anything() -> None:
    assert dv2_rules._excluded_rule_ids == frozenset()


# --- Backstop telemetry -------------------------------------------------------------------


def _events() -> list[llm.TraceEvent]:
    return []


def _sat(attributes: list[str], cdk: list[str]):
    from vault_agent.state import Satellite

    return Satellite(
        name="sat_person_address",
        parent="hub_person",
        description="addresses",
        sat_type="multi_active",
        attributes=attributes,
        child_dependent_key=cdk,
    )


def _model_payload(sat) -> dict:
    from vault_agent.state import Hub

    hub = Hub(
        name="hub_person", business_key="person id", source_entity="person",
        description="a person",
    )
    return {
        "hubs": [hub.model_dump()],
        "links": [],
        "satellites": [sat.model_dump()],
    }


def test_cdk_dedup_fires_one_backstop_event_with_the_dropped_attrs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    from vault_agent.state import VaultAgentState

    events = _events()
    llm.set_trace_recorder(events.append)
    try:
        sat = _sat(["street", "address_type"], ["address_type"])
        Dv2ModelerAgent()._validate_model(_model_payload(sat), VaultAgentState())
    finally:
        llm.set_trace_recorder(None)

    assert [event.kind for event in events] == ["backstop"]
    assert events[0].backstop_id == "attributes_without_cdk"
    assert events[0].detail["rule"] == "cdk_not_payload"
    assert events[0].detail["dropped"] == ["address_type"]


def test_clean_model_fires_no_backstop(monkeypatch: pytest.MonkeyPatch) -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    from vault_agent.state import VaultAgentState

    events = _events()
    llm.set_trace_recorder(events.append)
    try:
        sat = _sat(["street", "city"], ["address_type"])
        Dv2ModelerAgent()._validate_model(_model_payload(sat), VaultAgentState())
    finally:
        llm.set_trace_recorder(None)

    assert events == []  # a backstop that repairs nothing is not a fire


def test_backstop_is_a_no_op_without_a_recorder() -> None:
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    from vault_agent.state import VaultAgentState

    assert llm._default_trace_recorder is None
    sat = _sat(["street", "address_type"], ["address_type"])
    model = Dv2ModelerAgent()._validate_model(_model_payload(sat), VaultAgentState())

    assert model.satellites[0].attributes == ["street"]  # repair still happens, silently


def test_effsat_rejection_fires_a_backstop_event() -> None:
    from vault_agent.agents.code_generator import CodeGeneratorAgent
    from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState

    state = VaultAgentState()
    state.dv_model = DVModel(
        hubs=[
            Hub(
                name="hub_account", business_key="account number",
                source_entity="account", description="an account",
            ),
            Hub(
                name="hub_customer", business_key="customer id",
                source_entity="customer", description="a customer",
            ),
        ],
        links=[
            Link(
                name="link_account_customer",
                connected_hubs=["hub_account", "hub_customer"],
                description="account ownership",
                driving_key=["hub_account"],
            )
        ],
        satellites=[
            Satellite(
                name="sat_account_customer_eff",
                parent="link_account_customer",
                description="active period",
                sat_type="effectivity",
                attributes=["effective from", "effective to", "stray payload"],
            )
        ],
    )
    events = _events()
    llm.set_trace_recorder(events.append)
    try:
        import asyncio

        asyncio.run(CodeGeneratorAgent().run(state))
    finally:
        llm.set_trace_recorder(None)

    backstops = [event for event in events if event.kind == "backstop"]
    assert [event.backstop_id for event in backstops] == ["effsat_two_attributes"]
    assert backstops[0].detail["satellite"] == "sat_account_customer_eff"
    # The GENERATION_GAP flag stays the human-review channel; the event only adds counting.
    assert any(flag.asset == "sat_account_customer_eff" for flag in state.flags)


def test_fk_demotion_fires_a_backstop_event() -> None:
    from vault_agent.agents.source_mapper import SourceMapperAgent
    from vault_agent.state import SourceColumn, SourceTable, VaultAgentState

    state = VaultAgentState(
        source_schemas=[
            SourceTable(
                table="VICTOR_PARTNER",
                columns=[SourceColumn(name="PARTN_NR", comment="partner number")],
            ),
            SourceTable(
                table="VICTOR_VERTRAG",
                columns=[
                    SourceColumn(name="PARTN_NR", comment="FK to VICTOR_PARTNER.PARTN_NR")
                ],
            ),
        ]
    )
    agent = SourceMapperAgent()
    # The real _Concept, not an ad-hoc stub: concept identity is (label, entity) since WP32,
    # and a stub that only carries the label cannot exercise the lookup the agent performs.
    from vault_agent.agents.source_mapper import _Concept

    concepts = [_Concept("partner number", "hub_partner", "business_key")]
    raw = {
        "partner number": {
            "decision": "unresolved",
            "evidence": ["VICTOR_PARTNER.PARTN_NR", "VICTOR_VERTRAG.PARTN_NR"],
        }
    }
    events = _events()
    llm.set_trace_recorder(events.append)
    try:
        mapping = agent._post_validate(state, concepts, raw)
    finally:
        llm.set_trace_recorder(None)

    assert mapping.proposals and mapping.proposals[0].table == "VICTOR_PARTNER"
    assert [event.backstop_id for event in events] == ["fk_demotion"]
    assert events[0].detail["concept"] == "partner number"
    assert events[0].detail["demoted"] == ["VICTOR_VERTRAG.PARTN_NR"]


def test_steering_rule_is_frozen() -> None:
    rule = DV_MODELING_RULES[0]
    assert isinstance(rule, SteeringRule)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rule.id = "mutated"  # type: ignore[misc]


# --- WP20: the construct-naming rule ------------------------------------------------------


def test_construct_naming_rule_is_registered_and_gate_backed() -> None:
    """A deliberate WP20 addition: steering keeps a deterministic formality from burning a
    modeling retry, but E_BAD_NAME — not the prompt line — is the guarantee, so the rule
    carries no backstop (a backstop repairs; a gate refuses)."""
    rule = next(r for r in DV_MODELING_RULES if r.id == "construct_naming")
    assert rule.backstop is None
    assert "E_BAD_NAME" in rule.origin
    assert rule.text in _render_rules()


def test_construct_naming_rule_has_a_ledger_row() -> None:
    ledger = (
        Path(__file__).parents[1] / "docs" / "architecture" / "steering-ledger.md"
    ).read_text(encoding="utf-8")
    assert "`construct_naming`" in ledger


def test_the_wp23_steering_rule_was_deleted_by_adr_0011() -> None:
    """WP28: the rule told the modeler to avoid a shape ADR-0011 then blessed.

    Pinned so it cannot quietly come back: it measured 0/3 effective on the live
    bank_extension runs, and its target turned out to be the DV2.0-canonical form."""
    ids = {rule.id for rule in DV_MODELING_RULES}

    assert "no_source_table_on_multi_source_hub" not in ids
