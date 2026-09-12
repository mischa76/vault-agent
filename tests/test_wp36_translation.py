"""WP36 (ADR-0013): surrogate→natural-key translation for FK-derived links.

Keyless, against the miniature of the four AdventureWorks cases (`hub_product` keyed on
`ProductNumber`, `ShoppingCartItem.ProductID → Product.ProductID`). Each test is one clause of
the spec's §6: trigger and counter-case, the typed marker on the ratified link, the translation
model and its tests, the stage reading it, the gate, the flag, the checkpoint text.
"""
from __future__ import annotations

from tests.test_wp36_translation_guard import product_hub, shopping_cart_item
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.staging_generator import build_staging
from vault_agent.link_proposal import (
    apply_ratified_link_proposals,
    collect_link_proposals,
    propose_links,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    KeyTranslation,
    Link,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)


def _product_table(columns: list[str] | None = None) -> SourceTable:
    return SourceTable(
        table="Product", schema="Production",
        columns=columns or ["ProductID", "Name", "ProductNumber", "Color"],
    )


def _ratified_state(*, with_product: bool = False) -> VaultAgentState:
    schemas = [shopping_cart_item()] + ([_product_table()] if with_product else [])
    state = VaultAgentState(existing_model=product_hub(), source_schemas=schemas)
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    delta = DVModel(hubs=[Hub(name="hub_shopping_cart_item", business_key="ShoppingCartItemID",
                              source_entity="shopping cart item", description="A cart line.")])
    merged = apply_ratified_link_proposals(delta, product_hub(), state)
    state.dv_model = DVModel(hubs=[*product_hub().hubs, *merged.hubs], links=merged.links)
    return state


# --- trigger ------------------------------------------------------------------------------

def test_the_referenced_table_declared_with_both_columns_still_translates() -> None:
    proposals, skipped = propose_links(product_hub(), [shopping_cart_item(), _product_table()])
    assert skipped == [] and proposals.proposals[0].category == "declared_fk_translated"


def test_the_referenced_table_declared_without_the_natural_key_is_a_typed_skip() -> None:
    proposals, skipped = propose_links(
        product_hub(), [shopping_cart_item(), _product_table(["ProductID", "Name"])]
    )
    assert proposals.proposals == []
    assert [(s.asset, s.reason) for s in skipped] == [
        ("ShoppingCartItem.ProductID", "translation_key_missing")
    ]


def test_two_hubs_bound_to_the_referenced_table_do_not_trigger() -> None:
    vault = product_hub()
    vault.hubs.append(Hub(name="hub_product", business_key="Name", source_entity="dup",
                          description="a second hub on the same table (ambiguous)"))
    proposals, skipped = propose_links(vault, [shopping_cart_item()])
    assert proposals.proposals == [] and skipped[0].reason == "no_hub_for_key"


def test_the_evidence_says_join_not_alias() -> None:
    proposals, _ = propose_links(product_hub(), [shopping_cart_item()])
    joined = " ".join(proposals.proposals[0].evidence)
    assert "join" in joined and "not an alias" in joined


# --- the ratified link --------------------------------------------------------------------

def test_a_ratified_translation_becomes_a_link_carrying_the_typed_marker() -> None:
    state = _ratified_state()
    [link] = state.dv_model.links
    target = next(ref for ref in link.hub_refs if ref.hub == "hub_product")
    assert target.source_key_column is None
    assert isinstance(target.key_translation, KeyTranslation)
    assert target.key_translation.referencing_column == "ProductID"
    assert target.key_translation.natural_key_column == "PRODUCTNUMBER"


def test_applying_a_translation_raises_its_own_flag_kind_once() -> None:
    state = _ratified_state()
    flags = [f for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION]
    assert len(flags) == 1 and flags[0].asset == "ShoppingCartItem.ProductID"


# --- staging: translation model + stage on it ---------------------------------------------

def test_staging_renders_a_translation_model_and_stages_from_it() -> None:
    state = _ratified_state(with_product=True)
    result = build_staging(state.dv_model, state.source_schemas)
    link_stage = next(n for n in result.models if n.startswith("stg_shopping_cart_item_product"))
    via = f"{link_stage}_via_product"
    assert via in result.models
    sql = result.models[via]
    assert "left join" in sql and "r.PRODUCTNUMBER as PRODUCTNUMBER" in sql
    assert "on t.PRODUCTID = r.PRODUCTID" in sql
    assert "{{ source('raw', 'Product') }}" in sql  # the hub's own binding of Product
    assert f"source_model: '{via}'" in result.models[link_stage]
    assert "PRODUCTNUMBER" in result.models[link_stage]  # the FK hash is still over the natural key


def test_the_translation_model_ships_its_data_time_gates() -> None:
    state = _ratified_state(with_product=True)
    result = build_staging(state.dv_model, state.source_schemas)
    via = next(n for n in result.models if n.endswith("_via_product"))
    yml = result.scaffolding[f"models/staging/{via}.yml"]
    assert "- not_null" in yml and "relationships" in yml and "field: PRODUCTID" in yml


def test_the_metadata_records_the_join() -> None:
    state = _ratified_state(with_product=True)
    result = build_staging(state.dv_model, state.source_schemas)
    stage = next(n for n in result.metadata if n.startswith("stg_shopping_cart_item_product"))
    kt = result.metadata[stage]["key_translation"]
    assert kt["through_table"] == "Product" and kt["projects"] == "PRODUCTNUMBER"


def test_without_a_translation_no_translation_model_or_yml_appears() -> None:
    state = VaultAgentState(dv_model=DVModel(
        hubs=[Hub(name="hub_a", business_key="A", source_entity="a", description="a"),
              Hub(name="hub_b", business_key="B", source_entity="b", description="b")],
        links=[Link(name="link_a_b", description="plain",
                    connected_hubs=[LinkHubRef(hub="hub_a"), LinkHubRef(hub="hub_b")])],
    ))
    result = build_staging(state.dv_model, [])
    assert not any("_via_" in n for n in result.models)
    assert not any(p.endswith(".yml") and "_via_" in p for p in result.scaffolding)


# --- the gate -----------------------------------------------------------------------------

async def test_the_gate_refuses_a_translation_whose_surrogate_is_missing() -> None:
    from vault_agent.agents.validator import ValidatorAgent

    state = _ratified_state()
    state.source_schemas = [SourceTable(table="ShoppingCartItem", schema="Sales",
                                        columns=["ShoppingCartItemID", "Quantity"],
                                        foreign_keys=[])]
    report = (await ValidatorAgent().run(state)).validation_report
    codes = [i.code for i in report.issues if i.code == "E_LINK_KEY_NOT_IN_SOURCE"]
    assert codes, [i.code for i in report.issues]


async def test_the_gate_holds_when_the_surrogate_is_declared() -> None:
    from vault_agent.agents.validator import ValidatorAgent

    state = _ratified_state(with_product=True)
    report = (await ValidatorAgent().run(state)).validation_report
    assert not [i for i in report.issues if i.code == "E_LINK_KEY_NOT_IN_SOURCE"]


# --- the checkpoint text ------------------------------------------------------------------

def test_the_checkpoint_names_the_join() -> None:
    from vault_agent.cli import _link_category_note

    proposals, _ = propose_links(product_hub(), [shopping_cart_item()])
    note = _link_category_note(proposals.proposals[0])
    assert note == "declared_fk_translated: ProductID → PRODUCTNUMBER through Production.Product"


# --- the modeler must never see or author these -------------------------------------------

def test_the_modeler_tool_schema_hides_the_proposer_owned_fields() -> None:
    """2026-09-12: the moment `key_translation` existed, the modeler filled it (9 of 23 links
    in a paid production step). The fields belong to the ratified-proposal path only."""
    import json

    from vault_agent.agents.dv2_modeler import _tool_schema

    schema = json.dumps(_tool_schema())
    assert "key_translation" not in schema
    assert "source_key_column" not in schema
    assert "KeyTranslation" not in schema
    assert "role" in schema  # the legitimate LinkHubRef fields survive


async def test_the_gate_refuses_a_translation_no_proposal_produced() -> None:
    from vault_agent.agents.validator import ValidatorAgent

    state = _ratified_state(with_product=True)
    # Same link, but forget the ratified proposal: the translation is now authorless.
    state.link_proposals.proposals = []
    report = (await ValidatorAgent().run(state)).validation_report
    assert [i.code for i in report.issues if i.code == "E_LINK_TRANSLATION_UNRATIFIED"]


async def test_the_gate_accepts_the_translation_the_ratified_proposal_produced() -> None:
    from vault_agent.agents.validator import ValidatorAgent

    state = _ratified_state(with_product=True)
    report = (await ValidatorAgent().run(state)).validation_report
    assert not [i for i in report.issues if i.code == "E_LINK_TRANSLATION_UNRATIFIED"]
