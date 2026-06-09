"""Unit tests for the Validator agent.

The validator is deterministic (no LLM), so these tests assert exact verdicts and run in
CI without an Anthropic API key.
"""
from typing import Any

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    Artifacts,
    DVModel,
    Hub,
    Link,
    Satellite,
    VaultAgentState,
)


def _valid_model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="national customer ID",
                source_entity="customer", description="The customer."),
            Hub(name="hub_account", business_key="account number",
                source_entity="account", description="The account."),
        ],
        links=[
            Link(name="link_account_customer", connected_hubs=["hub_account", "hub_customer"],
                 description="Account ownership."),
        ],
        satellites=[
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["name"], description="Customer attributes."),
            Satellite(name="sat_account_details", parent="hub_account",
                      attributes=["balance"], description="Account attributes."),
        ],
    )


def _codes(report_issues: list[dict[str, Any]]) -> set[str]:
    return {issue["code"] for issue in report_issues}


async def test_valid_model_passes() -> None:
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_valid_model()))

    assert result.validation_report.passed is True
    assert not [i for i in result.validation_report.issues if i["severity"] == "error"]
    assert result.decisions[-1] == {
        "agent": "validator", "passed": True, "errors": 0, "warnings": 0,
    }


async def test_empty_model_fails() -> None:
    result = await ValidatorAgent().run(VaultAgentState())

    assert result.validation_report.passed is False
    assert "E_NO_HUBS" in _codes(result.validation_report.issues)


async def test_link_referencing_unknown_hub_fails() -> None:
    model = _valid_model()
    model.links.append(
        Link(name="link_ghost", connected_hubs=["hub_account", "hub_ghost"], description="x")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_LINK_UNKNOWN_HUB" in _codes(result.validation_report.issues)


async def test_satellite_unknown_parent_and_empty_payload_fail() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_orphan", parent="hub_missing", attributes=[], description="x")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    codes = _codes(result.validation_report.issues)
    assert result.validation_report.passed is False
    assert "E_SAT_UNKNOWN_PARENT" in codes
    assert "E_SAT_NO_PAYLOAD" in codes


async def test_duplicate_name_fails() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="hub_customer", parent="hub_account", attributes=["x"], description="dup")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_DUP_NAME" in _codes(result.validation_report.issues)


async def test_hub_without_satellite_warns_but_passes() -> None:
    model = _valid_model()
    model.hubs.append(
        Hub(name="hub_product", business_key="product code",
            source_entity="product", description="no sat hangs off this one")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    warnings = [i for i in result.validation_report.issues if i["severity"] == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w["code"] == "W_HUB_NO_SAT" and w["construct"] == "hub_product" for w in warnings)


async def test_generated_artifact_missing_column_fails() -> None:
    artifacts = Artifacts(
        automatedv_yaml={
            "hubs": {
                "hub_customer": {
                    "src_pk": "CUSTOMER_HK", "src_nk": "",  # missing business key column
                    "src_ldts": "LOAD_DATETIME", "src_source": "RECORD_SOURCE",
                }
            },
            "links": {},
            "satellites": {},
        }
    )
    state = VaultAgentState(dv_model=_valid_model(), artifacts=artifacts)
    result = await ValidatorAgent().run(state)

    missing = [i for i in result.validation_report.issues if i["code"] == "E_MISSING_COLUMN"]
    assert result.validation_report.passed is False
    assert any("business_key" in i["message"] for i in missing)
