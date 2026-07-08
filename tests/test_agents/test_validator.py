"""Unit tests for the Validator agent.

The validator is deterministic (no LLM), so these tests assert exact verdicts and run in
CI without an Anthropic API key.
"""
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    Artifacts,
    DVModel,
    Hub,
    Link,
    Satellite,
    SourceTable,
    ValidationIssue,
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


def _codes(report_issues: list[ValidationIssue]) -> set[str]:
    return {issue.code for issue in report_issues}


async def test_valid_model_passes() -> None:
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_valid_model()))

    assert result.validation_report.passed is True
    assert not [i for i in result.validation_report.issues if i.severity == "error"]
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

    warnings = [i for i in result.validation_report.issues if i.severity == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w.code == "W_HUB_NO_SAT" and w.construct == "hub_product" for w in warnings)


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


async def test_multi_active_satellite_without_source_table_warns_shared_grain() -> None:
    # WP7 §7.1: multi-active rows usually live in their own finer-grain relation;
    # sharing the parent's staging is only a warning — the model still passes.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_phones", parent="hub_customer",
                  attributes=["phone"], description="phone numbers",
                  sat_type="multi_active", child_dependent_key=["phone type"])
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is True
    issues = [i for i in result.validation_report.issues
              if i.code == "W_MASAT_SHARED_GRAIN"]
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].construct == "sat_customer_phones"


async def test_multi_active_satellite_with_source_table_does_not_warn() -> None:
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_phones", parent="hub_customer",
                  attributes=["phone"], description="phone numbers",
                  sat_type="multi_active", child_dependent_key=["phone type"],
                  source_table="raw_customer_phone")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert "W_MASAT_SHARED_GRAIN" not in _codes(result.validation_report.issues)


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


async def test_standard_sat_on_link_with_date_pair_warns_maybe_effectivity() -> None:
    # The reality-test slip: a *standard* sat on a link carrying [EFFECTIVE_FROM, EFFECTIVE_TO]
    # — it should be an effectivity sat. Heuristic warning, never a hard failure.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_ownership_effectivity", parent="link_account_customer",
                  attributes=["effective from", "effective to"],
                  description="ownership period as plain payload")  # sat_type defaults standard
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is True  # warning, not error
    assert "W_SAT_MAYBE_EFFECTIVITY" in _codes(result.validation_report.issues)


async def test_real_effectivity_sat_does_not_warn_maybe_effectivity() -> None:
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_effectivity_model()))

    assert "W_SAT_MAYBE_EFFECTIVITY" not in _codes(result.validation_report.issues)


async def test_standard_sat_on_hub_with_date_pair_does_not_warn() -> None:
    # Heuristic is scoped to links; a date pair on a hub sat is not flagged.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_window", parent="hub_customer",
                  attributes=["valid from", "valid to"], description="some hub-level window")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert "W_SAT_MAYBE_EFFECTIVITY" not in _codes(result.validation_report.issues)


async def test_standard_sat_on_link_without_date_pair_does_not_warn() -> None:
    # An ordinary degenerate-attribute sat on a link (no from/to pair) must not trip it.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_ownership_notes", parent="link_account_customer",
                  attributes=["sequence number", "note"], description="link payload")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert "W_SAT_MAYBE_EFFECTIVITY" not in _codes(result.validation_report.issues)


async def test_redundant_link_grain_warns() -> None:
    model = _valid_model()
    # A second link over the same hub set and type — same unit of work modeled twice.
    model.links.append(
        Link(name="link_customer_account_dup", connected_hubs=["hub_customer", "hub_account"],
             description="duplicate grain")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    warnings = [i for i in result.validation_report.issues if i.severity == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w.code == "W_LINK_REDUNDANT_GRAIN" for w in warnings)


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

    warnings = [i for i in result.validation_report.issues if i.severity == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w.code == "W_SAT_WIDE" and w.construct == "sat_customer_wide"
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

    warnings = [i for i in result.validation_report.issues if i.severity == "warning"]
    assert result.validation_report.passed is True  # warnings do not fail validation
    assert any(w.code == "W_BK_COLLISION_RISK" for w in warnings)


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

    missing = [i for i in result.validation_report.issues if i.code == "E_MISSING_COLUMN"]
    assert result.validation_report.passed is False
    assert any("business_key" in i.message for i in missing)


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
        i for i in result.validation_report.issues if i.code == "W_BK_NOT_IN_SOURCE"
    ]
    assert any(i.construct == "hub_customer" for i in bk_warnings)
    # Warning only — the model still passes (no error-severity issue introduced).
    assert result.validation_report.passed is True
    assert all(i.severity == "warning" for i in bk_warnings)


async def test_attribute_absent_from_source_is_warned() -> None:
    # "name" is not a declared customer column, so sat_customer_details's payload is ungrounded.
    schemas = [
        SourceTable(table="customer", columns=["national_customer_id"]),
        SourceTable(table="account", columns=["account_number", "balance"]),
    ]
    state = VaultAgentState(dv_model=_valid_model(), source_schemas=schemas)
    result = await ValidatorAgent().run(state)

    attr_warnings = [
        i for i in result.validation_report.issues if i.code == "W_ATTR_NOT_IN_SOURCE"
    ]
    assert any(
        i.construct == "sat_customer_details" and "'name'" in i.message
        for i in attr_warnings
    )


async def test_effectivity_reversed_date_order_fails() -> None:
    # The generator reads attributes[0] as start and attributes[1] as end; a recognisably
    # reversed pair would render a silently inverted effectivity satellite.
    model = _effectivity_model()
    model.satellites[-1].attributes = ["effective to", "effective from"]
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    reversed_issues = [
        i for i in result.validation_report.issues if i.code == "E_EFFSAT_DATE_ORDER"
    ]
    assert len(reversed_issues) == 1
    assert reversed_issues[0].construct == "sat_ownership_eff"
    assert "'effective to'" in reversed_issues[0].message
    assert "'effective from'" in reversed_issues[0].message
    assert "(start, end)" in reversed_issues[0].message


async def test_effectivity_unverifiable_date_order_warns() -> None:
    # Tokens the from/to heuristic cannot classify: warn, never hard-fail (same reasoning
    # as W_SAT_MAYBE_EFFECTIVITY — a heuristic non-match must not block a legitimate model).
    model = _effectivity_model()
    model.satellites[-1].attributes = ["first date", "second date"]
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is True
    warnings = [
        i for i in result.validation_report.issues
        if i.code == "W_EFFSAT_DATE_ORDER_UNVERIFIED"
    ]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert warnings[0].construct == "sat_ownership_eff"


async def test_effectivity_correct_date_order_emits_no_order_issue() -> None:
    result = await ValidatorAgent().run(VaultAgentState(dv_model=_effectivity_model()))

    codes = _codes(result.validation_report.issues)
    assert result.validation_report.passed is True
    assert "E_EFFSAT_DATE_ORDER" not in codes
    assert "W_EFFSAT_DATE_ORDER_UNVERIFIED" not in codes


async def test_satellite_duplicate_attribute_fails() -> None:
    # Lossy normalisation: "customer-id" and "customer id" both become CUSTOMER_ID — the
    # generated satellite would carry a duplicate payload column that Postgres rejects.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_ids", parent="hub_customer",
                  attributes=["customer-id", "customer id"], description="colliding labels")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    dups = [i for i in result.validation_report.issues if i.code == "E_SAT_DUP_ATTR"]
    assert len(dups) == 1
    assert dups[0].construct == "sat_customer_ids"
    assert "'customer-id'" in dups[0].message
    assert "'customer id'" in dups[0].message
    assert "CUSTOMER_ID" in dups[0].message


async def test_satellite_attribute_colliding_with_cdk_fails() -> None:
    # attributes + child_dependent_key are one column namespace on the satellite.
    model = _valid_model()
    model.satellites.append(
        Satellite(name="sat_customer_phones", parent="hub_customer",
                  attributes=["phone type", "number"], description="phones",
                  sat_type="multi_active", child_dependent_key=["phone-type"])
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    dups = [i for i in result.validation_report.issues if i.code == "E_SAT_DUP_ATTR"]
    assert len(dups) == 1
    assert dups[0].construct == "sat_customer_phones"
    assert "PHONE_TYPE" in dups[0].message


async def test_hubs_sharing_source_entity_with_different_bks_fail_hk_collision() -> None:
    # Both hubs derive PARTY_HK and stg_party from source_entity="party"; the staging
    # dedup would silently bind the second hub's hash key to the first hub's business key.
    model = _valid_model()
    model.hubs.extend([
        Hub(name="hub_person", business_key="person id",
            source_entity="party", description="a person"),
        Hub(name="hub_organisation", business_key="organisation id",
            source_entity="party", description="an organisation"),
    ])
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    collisions = [
        i for i in result.validation_report.issues if i.code == "E_HUB_HK_COLLISION"
    ]
    assert len(collisions) == 1
    assert collisions[0].construct == "hub_organisation, hub_person"  # sorted
    assert "PARTY_HK" in collisions[0].message


async def test_identical_hubs_fail_dup_hub() -> None:
    # Same business key AND same source entity: the same business concept modelled twice
    # ("one hub per business key"). Complements W_BK_COLLISION_RISK (different sources).
    model = _valid_model()
    model.hubs.append(
        Hub(name="hub_client", business_key="national customer ID",
            source_entity="customer", description="hub_customer modelled again")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    assert result.validation_report.passed is False
    dups = [i for i in result.validation_report.issues if i.code == "E_DUP_HUB"]
    assert len(dups) == 1
    assert dups[0].construct == "hub_client, hub_customer"  # sorted
    # Same source entity, so the cross-source collision-code warning must NOT fire.
    assert "W_BK_COLLISION_RISK" not in _codes(result.validation_report.issues)


async def test_identical_hubs_trip_only_dup_hub_not_hk_collision() -> None:
    # Gate 3/4 interplay: a same-BK group is excluded from E_HUB_HK_COLLISION by
    # construction — one pair of identical hubs yields exactly one E_DUP_HUB.
    model = _valid_model()
    model.hubs.append(
        Hub(name="hub_client", business_key="national customer ID",
            source_entity="customer", description="hub_customer modelled again")
    )
    result = await ValidatorAgent().run(VaultAgentState(dv_model=model))

    codes = _codes(result.validation_report.issues)
    assert "E_DUP_HUB" in codes
    assert "E_HUB_HK_COLLISION" not in codes


async def test_happy_path_trips_none_of_the_wp1_gates() -> None:
    # No-false-positive guard: the valid model and the valid effectivity setup produce
    # none of the four new codes.
    wp1_codes = {
        "E_EFFSAT_DATE_ORDER", "W_EFFSAT_DATE_ORDER_UNVERIFIED",
        "E_SAT_DUP_ATTR", "E_HUB_HK_COLLISION", "E_DUP_HUB",
    }
    for model in (_valid_model(), _effectivity_model()):
        result = await ValidatorAgent().run(VaultAgentState(dv_model=model))
        assert result.validation_report.passed is True
        assert not _codes(result.validation_report.issues) & wp1_codes
