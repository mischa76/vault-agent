"""Guard written FIRST, 2026-09-13: the re-model feedback for a hub collision names the hub to drop.

Two paid repeats of the WP30 rerun on 2026-09-13 exhausted their re-model loops on
`E_HUB_HK_COLLISION` — `hub_vendor` (AccountNumber) beside `hub_vendor_business_entity`
(BusinessEntityID), `hub_employee` beside `hub_employee_business_entity` — in 3 of the 4 such
steps observed. The business-key identifier had offered both candidates (0.95 against ~0.8),
the modeler hubbed both, and the feedback it got back was the diagnosis alone: "share source
entity … different business keys". Three attempts did not converge.

Pinned here: a deterministic remedy from `rules/`, computed from the business-key candidates
and the existing vault, carried on the issue as a typed field and sent to the modeler.
"""
from __future__ import annotations

import json

from tests.test_agents.test_dv2_modeler import StubExtractor, _state, _valid_payload
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import hub_collision_remedy
from vault_agent.state import (
    BusinessKeyCandidate,
    DVModel,
    Hub,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)


def _vendor() -> Hub:
    return Hub(name="hub_vendor", business_key="AccountNumber", source_entity="Vendor",
               description="A vendor.")


def _vendor_be() -> Hub:
    return Hub(name="hub_vendor_business_entity", business_key="BusinessEntityID",
               source_entity="Vendor", description="The vendor as a business entity.")


def _business_entity() -> Hub:
    return Hub(name="hub_business_entity", business_key="BusinessEntityID",
               source_entity="BusinessEntity", description="The party register.")


CANDIDATES = [
    BusinessKeyCandidate(entity="vendor", field="AccountNumber", score=0.95, rationale="r"),
    BusinessKeyCandidate(entity="vendor", field="BusinessEntityID", score=0.88, rationale="r"),
]


def test_the_higher_scored_candidate_keeps_its_hub() -> None:
    remedy = hub_collision_remedy([_vendor_be(), _vendor()], CANDIDATES, existing=None)
    assert remedy.keep == "hub_vendor" and remedy.drop == ["hub_vendor_business_entity"]
    assert not remedy.inherited
    assert "0.95" in remedy.text and "0.88" in remedy.text
    assert "hub_vendor_business_entity" in remedy.text and "link" in remedy.text


def test_without_candidates_the_hub_keyed_on_another_hubs_key_is_dropped() -> None:
    remedy = hub_collision_remedy(
        [_vendor(), _vendor_be()], [], existing=None, model_hubs=[_business_entity()]
    )
    assert remedy.keep == "hub_vendor" and remedy.drop == ["hub_vendor_business_entity"]
    assert "hub_business_entity" in remedy.text


def test_an_existing_hub_is_always_the_one_kept() -> None:
    existing = DVModel(hubs=[_vendor_be()])
    remedy = hub_collision_remedy([_vendor(), _vendor_be()], CANDIDATES, existing=existing)
    assert remedy.keep == "hub_vendor_business_entity" and remedy.drop == ["hub_vendor"]
    assert not remedy.inherited and "existing vault" in remedy.text


def test_a_pair_inherited_from_the_vault_is_named_as_unrepairable() -> None:
    existing = DVModel(hubs=[_vendor(), _vendor_be()])
    remedy = hub_collision_remedy([_vendor(), _vendor_be()], CANDIDATES, existing=existing)
    assert remedy.inherited and remedy.keep is None and remedy.drop == []
    assert "do not re-emit" in remedy.text


def test_a_key_the_identifier_never_proposed_loses_to_a_ranked_one() -> None:
    """The first replay: `hub_department` (Name) beside `hub_department_group` (GroupName)."""
    department = Hub(name="hub_department", business_key="Name", source_entity="Department",
                     description="A department.")
    group = Hub(name="hub_department_group", business_key="GroupName",
                source_entity="Department", description="A department group.")
    shift = Hub(name="hub_shift", business_key="Name", source_entity="Shift", description="s")
    remedy = hub_collision_remedy(
        [group, department],
        [BusinessKeyCandidate(entity="department", field="Name", score=0.95, rationale="r")],
        existing=None, model_hubs=[shift],
    )
    assert remedy.keep == "hub_department" and remedy.drop == ["hub_department_group"]
    assert "never proposed GroupName" in remedy.text
    assert "hub_shift" not in remedy.text  # a generic `Name` shared by name is no reference


def test_a_generic_shared_key_name_is_not_a_reference() -> None:
    department = Hub(name="hub_department", business_key="Name", source_entity="Department",
                     description="A department.")
    group = Hub(name="hub_department_group", business_key="GroupName",
                source_entity="Department", description="A department group.")
    shift = Hub(name="hub_shift", business_key="Name", source_entity="Shift", description="s")
    remedy = hub_collision_remedy([department, group], [], existing=None, model_hubs=[shift])
    assert "arbitrary" in remedy.text and "hub_shift" not in remedy.text


async def test_the_validator_carries_the_remedy_on_the_collision_issue() -> None:
    state = VaultAgentState(
        dv_model=DVModel(hubs=[_business_entity(), _vendor(), _vendor_be()]),
        business_keys=CANDIDATES,
    )
    report = (await ValidatorAgent().run(state)).validation_report
    [issue] = [i for i in report.issues if i.code == "E_HUB_HK_COLLISION"]
    assert issue.remedy is not None
    assert issue.remedy.startswith("drop hub_vendor_business_entity")


async def test_the_modeler_sends_the_remedy_beside_the_three_fields() -> None:
    stub = StubExtractor(_valid_payload())
    state = _state()
    state.validation_report = ValidationReport(passed=False, issues=[
        ValidationIssue(severity="error", code="E_HUB_HK_COLLISION",
                        construct="hub_vendor, hub_vendor_business_entity",
                        message="hubs … share source entity",
                        remedy="drop hub_vendor_business_entity"),
        ValidationIssue(severity="error", code="E_SAT_ATTR_OVERLAP", construct="hub_vendor",
                        message="attribute twice"),
    ])
    await Dv2ModelerAgent(extractor=stub).run(state)
    payload = json.loads(stub.calls[0][1])
    first, second = payload["previous_validation_issues"]
    assert first["remedy"] == "drop hub_vendor_business_entity"
    assert set(second) == {"code", "construct", "message"}
