"""WP57 — the retry carries the previous model (spec §3). Committed before the change, failing."""
from __future__ import annotations

import json

from tests.test_agents.test_dv2_modeler import StubExtractor, _state, _valid_payload
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.rules.dv2_rules import active_modeling_rules
from vault_agent.state import DVModel, Hub, ValidationIssue, ValidationReport


async def test_a_first_attempt_sends_no_previous_model_and_records_its_delta() -> None:
    stub = StubExtractor(_valid_payload())
    state = await Dv2ModelerAgent(extractor=stub).run(_state())
    _, payload_json = stub.calls[0]
    assert "previous_model" not in json.loads(payload_json)
    assert state.previous_delta is not None
    assert [h.name for h in state.previous_delta.hubs] == [h.name for h in state.dv_model.hubs]


async def test_a_retry_carries_the_previous_delta_as_previous_model() -> None:
    state = _state()
    state.previous_delta = DVModel.model_validate(_valid_payload())
    state.validation_report = ValidationReport(passed=False, issues=[
        ValidationIssue(severity="error", code="E_HUB_NO_BK", construct="hub_account", message="m")
    ])
    stub = StubExtractor(_valid_payload())
    await Dv2ModelerAgent(extractor=stub).run(state)
    payload = json.loads(stub.calls[0][1])
    assert "previous_validation_issues" in payload
    previous = payload["previous_model"]
    assert [h["name"] for h in previous["hubs"]] == ["hub_customer", "hub_account"]
    assert [s["name"] for s in previous["satellites"]] == [
        s.name for s in state.previous_delta.satellites
    ]


async def test_in_brownfield_mode_the_previous_model_is_the_delta_not_the_vault() -> None:
    state = _state()
    state.existing_model = DVModel(hubs=[
        Hub(name="hub_legacy", business_key="legacy_id", source_entity="legacy", description="l")
    ])
    stub = StubExtractor(_valid_payload())
    state = await Dv2ModelerAgent(extractor=stub).run(state)
    assert state.previous_delta is not None
    assert "hub_legacy" not in [h.name for h in state.previous_delta.hubs]
    assert "hub_legacy" in [h.name for h in state.dv_model.hubs]  # merged vault keeps it


def test_the_repair_line_is_an_active_steering_rule() -> None:
    rule = next(r for r in active_modeling_rules() if r.id == "repair_not_redraft")
    assert "previous_model" in rule.text
