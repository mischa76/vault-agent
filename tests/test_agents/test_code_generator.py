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


async def test_non_standard_satellite_is_flagged_not_generated() -> None:
    model = _model()
    model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["address"], description="multi-active addresses",
                  sat_type="multi_active")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "sat_customer_addresses" not in result.artifacts.dbt_models
    assert any("ma_sat" in e and "human review" in e for e in result.errors)


async def test_transactional_link_is_flagged_not_generated() -> None:
    model = _model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional")
    )
    result = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))

    assert "link_transaction" not in result.artifacts.dbt_models
    assert any("t_link" in e and "human review" in e for e in result.errors)


async def test_no_hubs_short_circuits() -> None:
    result = await CodeGeneratorAgent().run(VaultAgentState())

    assert result.artifacts.dbt_models == {}
    assert any("no hubs" in e for e in result.errors)
