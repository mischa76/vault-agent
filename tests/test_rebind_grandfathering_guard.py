"""The source mapper's re-bind must keep WP23 §2.6 grandfathering (found 2026-09-17).

`code_generator` builds staging with ``existing=state.existing_model``, so a feed the extended
vault already materialised as ``stg_<entity>`` keeps that name and its binding. `rebind_staging`
— run by the source mapper and on the HITL resume — rebuilt staging WITHOUT it, so any re-bind in
a brownfield run renamed the grandfathered model to ``stg_<entity>_<source>`` and bound it
verbatim to the feed's table, while the raw-vault hub, generated before, still selects from
``stg_<entity>``. On a warehouse: a missing relation, or a renamed model dropped and rebuilt.

* ``test_a_rebind_keeps_the_grandfathered_staging_name_and_binding`` — FLIPPED by the fix; pinned
  first as today's defect.
* ``test_a_rebind_in_greenfield_is_unchanged`` — never flipped: no existing vault, nothing
  grandfathered, the re-bind as before.
"""
from __future__ import annotations

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.state import (
    DVModel,
    Hub,
    HubSource,
    Proposal,
    ProposedMapping,
    SourceTable,
    VaultAgentState,
)


def _existing() -> DVModel:
    return DVModel(hubs=[
        Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
            description="The customer."),
    ])


def _delta() -> DVModel:
    """The extension adds a second feed to the existing hub, and a new hub the mapper binds."""
    return DVModel(hubs=[
        Hub(name="hub_customer", business_key="customer_id", source_entity="crm_contact",
            description="", sources=[HubSource(source_table="crm_contact",
                                               business_key_column="customer_id")]),
        Hub(name="hub_order", business_key="order_no", source_entity="order",
            description="An order."),
    ])


def _schemas() -> list[SourceTable]:
    return [
        SourceTable(table="crm_contact", columns=["customer_id", "email"]),
        SourceTable(table="sales_order_header", columns=["order_no", "customer_id"]),
    ]


def _mapping() -> ProposedMapping:
    """The mapper's answer for the new hub: the only thing that makes the re-bind fire here."""
    return ProposedMapping(proposals=[Proposal(
        concept="order_no", entity="order", table="sales_order_header", column="order_no",
        confidence=0.95, category="exact_name", ratification_status="accepted",
    )])


async def _generated(existing: DVModel | None) -> VaultAgentState:
    state = VaultAgentState(existing_model=existing, source_schemas=_schemas())
    state.dv_model = merge_models(existing, _delta(), state) if existing else _delta()
    state = await CodeGeneratorAgent().run(state)
    state.mappings = _mapping()
    return state


async def test_a_rebind_keeps_the_grandfathered_staging_name_and_binding() -> None:
    state = await _generated(_existing())
    generated = dict(state.artifacts.staging_models)
    assert "stg_customer" in generated and "stg_customer_crm_contact" in generated
    assert "stg_customer" in state.artifacts.dbt_models["hub_customer"]

    rebind_staging(state)

    assert "sales_order_header" in state.artifacts.staging_models["stg_order"]  # it did fire
    # Flipped by the fix (pinned at 788bfae as: `stg_customer` gone, `stg_customer_customer`
    # present). The grandfathered model keeps its name and what it reads.
    assert set(state.artifacts.staging_models) == set(generated)
    assert state.artifacts.staging_models["stg_customer"] == generated["stg_customer"]
    assert set(state.artifacts.automatedv_yaml["staging"]) == set(generated)


async def test_a_rebind_in_greenfield_is_unchanged() -> None:
    state = await _generated(None)
    generated = dict(state.artifacts.staging_models)

    rebind_staging(state)

    assert "sales_order_header" in state.artifacts.staging_models["stg_order"]
    assert set(state.artifacts.staging_models) == set(generated)
