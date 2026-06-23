"""Unit tests for the Code Generator agent.

The generator is deterministic (no LLM), so these tests assert exact output and run in CI
without an Anthropic API key.
"""
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState


def _model() -> DVModel:
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
                      attributes=["customer name", "date of birth"],
                      description="Customer attributes."),
        ],
    )


def _state() -> VaultAgentState:
    return VaultAgentState(dv_model=_model())


async def test_generates_a_model_per_construct() -> None:
    result = await CodeGeneratorAgent().run(_state())

    assert set(result.artifacts.dbt_models) == {
        "hub_customer", "hub_account", "link_account_customer", "sat_customer_details",
    }
    assert not result.errors
    assert result.decisions[-1] == {
        "agent": "code_generator", "models_generated": 4,
        "hubs": 2, "links": 1, "satellites": 1,
    }


async def test_hub_sql_is_automatedv_idiomatic() -> None:
    result = await CodeGeneratorAgent().run(_state())
    sql = result.artifacts.dbt_models["hub_customer"]

    assert "{{ config(materialized='incremental') }}" in sql
    assert '{%- set src_pk = "CUSTOMER_HK" -%}' in sql
    assert '{%- set src_nk = "NATIONAL_CUSTOMER_ID" -%}' in sql
    assert '{%- set source_model = "stg_customer" -%}' in sql
    assert "automate_dv.hub(" in sql


async def test_link_resolves_foreign_keys_from_hubs() -> None:
    result = await CodeGeneratorAgent().run(_state())
    sql = result.artifacts.dbt_models["link_account_customer"]

    assert '{%- set src_pk = "LINK_ACCOUNT_CUSTOMER_HK" -%}' in sql
    assert '{%- set src_fk = ["ACCOUNT_HK", "CUSTOMER_HK"] -%}' in sql
    assert "automate_dv.link(" in sql
    # Metadata mirrors the SQL.
    assert result.artifacts.automatedv_yaml["links"]["link_account_customer"]["src_fk"] == [
        "ACCOUNT_HK", "CUSTOMER_HK",
    ]


async def test_satellite_payload_and_hashdiff() -> None:
    result = await CodeGeneratorAgent().run(_state())
    sql = result.artifacts.dbt_models["sat_customer_details"]

    assert '{%- set src_pk = "CUSTOMER_HK" -%}' in sql  # parent hub hashkey
    assert '{%- set src_hashdiff = "CUSTOMER_DETAILS_HASHDIFF" -%}' in sql
    assert '{%- set src_payload = ["CUSTOMER_NAME", "DATE_OF_BIRTH"] -%}' in sql
    assert "automate_dv.sat(" in sql


async def test_satellite_on_link_parent_resolves_link_hashkey() -> None:
    model = _model()
    model.satellites.append(
        Satellite(name="sat_ownership_effectivity", parent="link_account_customer",
                  attributes=["valid from", "valid to"], description="effectivity")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    sql = result.artifacts.dbt_models["sat_ownership_effectivity"]

    assert '{%- set src_pk = "LINK_ACCOUNT_CUSTOMER_HK" -%}' in sql
    assert not result.errors


async def test_multi_active_satellite_without_cdk_is_flagged() -> None:
    model = _model()
    model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["address"], description="multi-active addresses",
                  sat_type="multi_active")  # no child_dependent_key
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "sat_customer_addresses" not in result.artifacts.dbt_models
    assert any("child_dependent_key" in e and "ma_sat" in e for e in result.errors)


async def test_multi_active_satellite_generates_with_cdk() -> None:
    model = _model()
    model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["address line", "city"], description="addresses",
                  sat_type="multi_active", child_dependent_key=["address type"])
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    sql = result.artifacts.dbt_models["sat_customer_addresses"]

    assert "automate_dv.ma_sat(" in sql
    assert '{%- set src_cdk = ["ADDRESS_TYPE"] -%}' in sql
    assert '{%- set src_payload = ["ADDRESS_LINE", "CITY"] -%}' in sql
    assert not result.errors


def _eff_model(connected_hubs: list[str], driving_key: list[str]) -> DVModel:
    """A model whose single link carries an effectivity satellite, parameterised by the
    link's connected_hubs order and declared driving_key."""
    model = _model()
    model.links[0].connected_hubs = connected_hubs
    model.links[0].driving_key = driving_key
    model.satellites.append(
        Satellite(name="sat_ownership_eff", parent="link_account_customer",
                  attributes=["effective from", "effective to"], description="effectivity",
                  sat_type="effectivity")
    )
    return model


async def test_effectivity_satellite_applies_declared_driving_key() -> None:
    # driving_key names hub_customer, which is *second* in connected_hubs: src_dfk must
    # follow the declared driving key, not the connection order.
    model = _eff_model(["hub_account", "hub_customer"], ["hub_customer"])
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    sql = result.artifacts.dbt_models["sat_ownership_eff"]

    assert "automate_dv.eff_sat(" in sql
    # Auto end-dating must be enabled — it is what closes a superseded relationship.
    assert "is_auto_end_dating=true" in sql
    assert '{%- set src_pk = "LINK_ACCOUNT_CUSTOMER_HK" -%}' in sql
    assert '{%- set src_dfk = "CUSTOMER_HK" -%}' in sql  # declared driving key, not first hub
    assert '{%- set src_sfk = ["ACCOUNT_HK"] -%}' in sql
    assert '{%- set src_start_date = "EFFECTIVE_FROM" -%}' in sql
    assert '{%- set src_end_date = "EFFECTIVE_TO" -%}' in sql
    # src_eff MUST be a dedicated column distinct from src_start_date — reusing EFFECTIVE_FROM
    # breaks AutomateDV's incremental eff_sat SQL on Postgres ("specified more than once").
    assert '{%- set src_eff = "APPLIED_DTS" -%}' in sql
    assert not result.errors
    meta = result.artifacts.automatedv_yaml["satellites"]["sat_ownership_eff"]
    assert meta["src_dfk"] == "CUSTOMER_HK"
    assert meta["src_eff"] == "APPLIED_DTS"
    assert meta["src_eff"] != meta["src_start_date"]  # the decoupling that fixes incremental
    assert meta["src_sfk"] == ["ACCOUNT_HK"]


async def test_effectivity_driving_key_is_order_independent() -> None:
    # Reordering connected_hubs must not change src_dfk as long as driving_key is unchanged.
    reordered = await CodeGeneratorAgent().run(
        VaultAgentState(dv_model=_eff_model(["hub_customer", "hub_account"], ["hub_customer"]))
    )
    sql = reordered.artifacts.dbt_models["sat_ownership_eff"]

    assert '{%- set src_dfk = "CUSTOMER_HK" -%}' in sql
    assert '{%- set src_sfk = ["ACCOUNT_HK"] -%}' in sql
    assert not reordered.errors


async def test_effectivity_multi_hub_driving_key_renders_a_list() -> None:
    # A driving key spanning several hubs renders src_dfk as a list, like src_fk / src_cdk.
    model = _eff_model(["hub_account", "hub_customer"], ["hub_account", "hub_customer"])
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    sql = result.artifacts.dbt_models["sat_ownership_eff"]

    assert '{%- set src_dfk = ["ACCOUNT_HK", "CUSTOMER_HK"] -%}' in sql
    assert '{%- set src_sfk = [] -%}' in sql
    assert result.artifacts.automatedv_yaml["satellites"]["sat_ownership_eff"]["src_dfk"] == [
        "ACCOUNT_HK", "CUSTOMER_HK",
    ]
    assert not result.errors


async def test_effectivity_without_driving_key_is_flagged() -> None:
    # Empty driving_key at generation time: flag for human review, emit no SQL — never
    # silently fall back to the first connected hub.
    model = _eff_model(["hub_account", "hub_customer"], [])
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "sat_ownership_eff" not in result.artifacts.dbt_models
    assert any("no driving_key" in e and "sat_ownership_eff" in e for e in result.errors)


async def test_effectivity_satellite_on_hub_is_flagged() -> None:
    model = _model()
    model.satellites.append(
        Satellite(name="sat_bad_eff", parent="hub_customer",
                  attributes=["a", "b"], description="eff on a hub", sat_type="effectivity")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "sat_bad_eff" not in result.artifacts.dbt_models
    assert any("must hang off a generated link" in e for e in result.errors)


async def test_transactional_link_without_event_timestamp_is_flagged() -> None:
    model = _model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional")  # no event_timestamp
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "link_transaction" not in result.artifacts.dbt_models
    assert any("event_timestamp" in e and "nh_link" in e for e in result.errors)


async def test_transactional_link_generates_nh_link() -> None:
    model = _model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional",
             payload=["amount", "reference text"], event_timestamp="transaction timestamp")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    sql = result.artifacts.dbt_models["link_transaction"]

    assert "automate_dv.nh_link(" in sql
    assert '{%- set src_fk = ["ACCOUNT_HK", "CUSTOMER_HK"] -%}' in sql
    assert '{%- set src_payload = ["AMOUNT", "REFERENCE_TEXT"] -%}' in sql
    assert '{%- set src_eff = "TRANSACTION_TIMESTAMP" -%}' in sql
    assert not result.errors


async def test_satellite_column_collision_is_warned() -> None:
    # "customer-id" and "customer id" both normalise to CUSTOMER_ID — a silent overwrite
    # in the payload. The generator still emits SQL but flags the collision (L-2).
    model = _model()
    model.satellites.append(
        Satellite(name="sat_customer_ids", parent="hub_customer",
                  attributes=["customer-id", "customer id"], description="colliding labels")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "sat_customer_ids" in result.artifacts.dbt_models  # generation continues
    assert any(
        "collision" in e and "'customer-id'" in e and "'customer id'" in e
        and "CUSTOMER_ID" in e and "sat_customer_ids" in e
        for e in result.errors
    )


async def test_transactional_link_column_collision_is_warned() -> None:
    model = _model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional",
             payload=["ref no", "ref-no"], event_timestamp="ts")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "link_transaction" in result.artifacts.dbt_models
    assert any(
        "collision" in e and "REF_NO" in e and "link_transaction" in e
        for e in result.errors
    )


async def test_distinct_columns_do_not_warn() -> None:
    # The happy-path model has no colliding labels; no spurious collision warnings.
    result = await CodeGeneratorAgent().run(_state())
    assert not any("collision" in e for e in result.errors)


async def test_no_hubs_short_circuits() -> None:
    result = await CodeGeneratorAgent().run(VaultAgentState())

    assert result.artifacts.dbt_models == {}
    assert any("no hubs" in e for e in result.errors)
