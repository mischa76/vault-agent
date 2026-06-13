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
    SourceTable,
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


def _effectivity_model() -> DVModel:
    """A correct effectivity setup: a link with a driving key and a two-date eff sat."""
    model = _valid_model()
    model.links[0].driving_key = ["hub_account"]
    model.satellites.append(
        Satellite(name="sat_ownership_eff", parent="link_account_customer",
                  attributes=["effective from", "effective to"],
                  description="ownership effectivity", sat_type="effectivity")
    )
    return model


async def test_valid_effectivity_setup_passes() -> None:
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_effectivity_model()))

    codes = _codes(result.validation_report.issues)
    assert result.validation_report.passed is True
    assert not codes & {
        "E_EFFSAT_DATES", "E_EFFSAT_NO_DRIVING_KEY", "E_EFFSAT_PARENT_NOT_LINK",
        "E_DRIVING_KEY_NOT_IN_LINK",
    }


async def test_transactional_link_without_timestamp_fails() -> None:
    model = _valid_model()
    model.links.append(
        Link(name="link_payment", connected_hubs=["hub_account", "hub_customer"],
             description="a payment event", link_type="transactional")  # no event_timestamp
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_TXNLINK_NO_TIMESTAMP" in _codes(result.validation_report.issues)


async def test_multi_active_satellite_without_cdk_fails() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_phones", parent="hub_customer",
                  attributes=["phone"], description="phone numbers",
                  sat_type="multi_active")  # no child_dependent_key
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_MASAT_NO_CDK" in _codes(result.validation_report.issues)


async def test_effectivity_satellite_on_hub_fails() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_eff", parent="hub_customer",
                  attributes=["effective from", "effective to"],
                  description="eff hung off a hub", sat_type="effectivity")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_EFFSAT_PARENT_NOT_LINK" in _codes(result.validation_report.issues)


async def test_effectivity_satellite_wrong_date_count_fails() -> None:
    model = _effectivity_model()
    model.satellites[-1].attributes = ["effective from"]  # only one date, not two
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_EFFSAT_DATES" in _codes(result.validation_report.issues)


async def test_effectivity_satellite_without_driving_key_fails() -> None:
    model = _effectivity_model()
    model.links[0].driving_key = []  # parent link declares no driving key
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_EFFSAT_NO_DRIVING_KEY" in _codes(result.validation_report.issues)


async def test_driving_key_not_subset_of_link_fails() -> None:
    model = _valid_model()
    model.links[0].driving_key = ["hub_ghost"]  # not among connected_hubs
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    assert "E_DRIVING_KEY_NOT_IN_LINK" in _codes(result.validation_report.issues)


async def test_redundant_link_grain_warns() -> None:
    model = _valid_model()
    # A second link over the same hub set and type — same unit of work modeled twice.
    model.links.append(
        Link(name="link_customer_account_dup", connected_hubs=["hub_customer", "hub_account"],
             description="duplicate grain")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    warnings = [i for i in result.validation_report.issues if i["severity"] == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w["code"] == "W_LINK_REDUNDANT_GRAIN" for w in warnings)


async def test_attribute_overlap_across_satellites_fails() -> None:
    model = _valid_model()
    # 'name' already lives in sat_customer_details on hub_customer; repeat it elsewhere.
    model.satellites.append(
        Satellite(name="sat_customer_extra", parent="hub_customer",
                  attributes=["name", "segment"], description="overlapping payload")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    codes = _codes(result.validation_report.issues)
    assert result.validation_report.passed is False
    assert "E_SAT_ATTR_OVERLAP" in codes


async def test_wide_satellite_warns() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_wide", parent="hub_customer",
                  attributes=[f"attr_{i}" for i in range(31)],  # over the threshold of 30
                  description="too wide")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    warnings = [i for i in result.validation_report.issues if i["severity"] == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w["code"] == "W_SAT_WIDE" and w["construct"] == "sat_customer_wide"
               for w in warnings)


async def test_business_key_collision_across_sources_warns() -> None:
    model = _valid_model()
    # Same business-key field ('account number') over a different source entity.
    model.hubs.append(
        Hub(name="hub_ledger_account", business_key="account number",
            source_entity="ledger", description="ledger account, same key field")
    )
    model.satellites.append(
        Satellite(name="sat_ledger_account_details", parent="hub_ledger_account",
                  attributes=["ledger code"], description="ledger account attributes")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    warnings = [i for i in result.validation_report.issues if i["severity"] == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w["code"] == "W_BK_COLLISION_RISK" for w in warnings)


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


def _grounded_schemas() -> list[SourceTable]:
    # Columns match the _valid_model() business keys and attributes after normalisation:
    # "national customer ID" -> NATIONAL_CUSTOMER_ID, "name" -> NAME, etc.
    return [
        SourceTable(table="customer",
                    columns=["national_customer_id", "name"]),
        SourceTable(table="account",
                    columns=["account_number", "balance"]),
    ]


async def test_no_source_schema_emits_no_grounding_warnings() -> None:
    # Regression guard: with no declared schema, grounding is inert — same verdict as before.
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_valid_model()))

    codes = _codes(result.validation_report.issues)
    assert "W_BK_NOT_IN_SOURCE" not in codes
    assert "W_ATTR_NOT_IN_SOURCE" not in codes


async def test_grounded_model_emits_no_grounding_warnings() -> None:
    state = VaultAgentState(dv_model=_valid_model(), source_schemas=_grounded_schemas())
    result = await ValidatorAgent().run(state)

    codes = _codes(result.validation_report.issues)
    assert "W_BK_NOT_IN_SOURCE" not in codes
    assert "W_ATTR_NOT_IN_SOURCE" not in codes


async def test_business_key_absent_from_source_is_warned() -> None:
    # Drop "national_customer_id" from the customer table: hub_customer's key is now ungrounded.
    schemas = [
        SourceTable(table="customer", columns=["name"]),
        SourceTable(table="account", columns=["account_number", "balance"]),
    ]
    state = VaultAgentState(dv_model=_valid_model(), source_schemas=schemas)
    result = await ValidatorAgent().run(state)

    bk_warnings = [
        i for i in result.validation_report.issues if i["code"] == "W_BK_NOT_IN_SOURCE"
    ]
    assert any(i["construct"] == "hub_customer" for i in bk_warnings)
    # Warning only — the model still passes (no error-severity issue introduced).
    assert result.validation_report.passed is True
    assert all(i["severity"] == "warning" for i in bk_warnings)


async def test_attribute_absent_from_source_is_warned() -> None:
    # "name" is not a declared customer column, so sat_customer_details's payload is ungrounded.
    schemas = [
        SourceTable(table="customer", columns=["national_customer_id"]),
        SourceTable(table="account", columns=["account_number", "balance"]),
    ]
    state = VaultAgentState(dv_model=_valid_model(), source_schemas=schemas)
    result = await ValidatorAgent().run(state)

    attr_warnings = [
        i for i in result.validation_report.issues if i["code"] == "W_ATTR_NOT_IN_SOURCE"
    ]
    assert any(
        i["construct"] == "sat_customer_details" and "'name'" in i["message"]
        for i in attr_warnings
    )
