"""WP40 — key licenses, keyless, on the production miniature (spec §4)."""
from __future__ import annotations

import json

from tests.test_wp40_key_license_guard import (
    prior_vault,
    production_delta,
    production_schema,
    production_state,
    run_production,
)
from vault_agent.agents.dv2_modeler import _tool_schema
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.link_proposal import (
    collect_link_proposals,
    pending_link_decisions,
    proposal_key,
    propose_links,
)
from vault_agent.state import FlagKind, SourceTable, VaultAgentState


def test_a_key_into_an_unhubbed_table_of_the_increment_is_a_pending_license() -> None:
    proposals, skipped = propose_links(prior_vault(), production_schema())
    keys = {proposal_key(lic): lic for lic in proposals.licenses}
    assert {"ProductCostHistory.ProductID", "ProductInventory.ProductID",
            "ProductInventory.LocationID"} <= set(keys)
    assert keys["ProductCostHistory.ProductID"].target_hub is None
    assert "ProductCostHistory.ProductID" not in [s.asset for s in skipped]


def test_a_license_is_decided_like_a_link_and_listed_as_pending() -> None:
    state = VaultAgentState(existing_model=prior_vault(), source_schemas=production_schema())
    collect_link_proposals(state)
    assert "ProductCostHistory.ProductID" in [
        proposal_key(p) for p in pending_link_decisions(state.link_proposals)
    ]
    apply_link_decision(state, {"links": {"ProductCostHistory.ProductID": False}})
    [lic] = [x for x in state.link_proposals.licenses
             if proposal_key(x) == "ProductCostHistory.ProductID"]
    assert lic.ratification_status == "overridden"


async def test_a_declined_license_repairs_nothing() -> None:
    from tests.test_agents.test_dv2_modeler import StubExtractor
    from vault_agent.agents.code_generator import CodeGeneratorAgent
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    from vault_agent.agents.validator import ValidatorAgent

    state = VaultAgentState(existing_model=prior_vault(), source_schemas=production_schema(),
                            business_keys=production_state().business_keys,
                            requirements=production_state().requirements)
    collect_link_proposals(state)
    apply_link_decision(state, {"links": {"ProductCostHistory.ProductID": False}, "accept": True})
    stub = StubExtractor(production_delta(with_link=False))
    state = await Dv2ModelerAgent(extractor=stub).run(state)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_product_cost_history"]
    assert sat.key_translation is None
    assert "E_SAT_KEY_NOT_IN_SOURCE" in {i.code for i in state.validation_report.issues}


async def test_the_resolution_is_recorded_on_the_license_and_marked_as_the_applier_s() -> None:
    state = await run_production(production_delta(with_link=False))
    [lic] = [x for x in state.link_proposals.licenses
             if proposal_key(x) == "ProductCostHistory.ProductID"]
    assert lic.target_hub == "hub_product" and lic.resolved_by_applier
    assert lic.key_translation is not None and lic.key_translation.through_table == "Product"


async def test_link_participations_and_link_satellites_are_repaired_and_flagged() -> None:
    state = await run_production(production_delta())
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_product_inventory"]
    translated = {ref.hub for ref in link.hub_refs if ref.key_translation is not None}
    assert translated == {"hub_product", "hub_location"}
    [sat] = [s for s in state.dv_model.satellites if s.name == "sat_product_inventory_details"]
    assert set(sat.participation_translations) == {"hub_product", "hub_location"}
    assert sum(1 for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION) >= 2
    assert "sat_product_inventory_details" in {
        f.asset for f in state.flags if f.kind == FlagKind.SAT_TRANSLATION
    }
    assert not [i.code for i in state.validation_report.issues
                if i.code in ("E_SAT_KEY_NOT_IN_SOURCE", "E_SAT_TRANSLATION_UNRATIFIED",
                              "E_LINK_TRANSLATION_UNRATIFIED", "E_LINK_KEY_NOT_IN_SOURCE")]


async def test_the_link_satellite_stage_reads_one_view_with_both_joins() -> None:
    state = await run_production(production_delta())
    stage = state.artifacts.staging_models["stg_product_inventory_details"]
    assert "_via_" in stage
    view_name = stage.split("source_model: '")[1].split("'")[0]
    view = state.artifacts.staging_models[view_name]
    assert view.count("left join") == 2 and "PRODUCTNUMBER" in view and ".NAME as NAME" in view


async def test_a_renamed_key_repairs_a_link_by_alias() -> None:
    schema = production_schema()
    schema.append(SourceTable(table="ProductDocument", columns=["ProductNumberRef", "DocumentNode"],
                              foreign_keys=[{"columns": ["ProductNumberRef"],
                                             "references_table": "Product",
                                             "references_columns": ["ProductNumber"]}]))
    state = VaultAgentState(existing_model=prior_vault(), source_schemas=schema,
                            business_keys=production_state().business_keys,
                            requirements=production_state().requirements)
    collect_link_proposals(state)
    apply_link_decision(state, {"accept": True})
    payload = production_delta(with_link=False)
    payload["hubs"].append({"name": "hub_document", "business_key": "DocumentNode",
                            "source_entity": "Document", "description": "A document."})
    payload["links"].append({"name": "link_product_document",
                             "connected_hubs": ["hub_product", "hub_document"],
                             "description": "Documents of a product."})
    from tests.test_agents.test_dv2_modeler import StubExtractor
    from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_product_document"]
    [ref] = [r for r in link.hub_refs if r.hub == "hub_product"]
    assert ref.source_key_column == "ProductNumberRef" and ref.key_translation is None


async def test_the_modeler_never_sees_the_participation_translations_field() -> None:
    assert "participation_translations" not in json.dumps(_tool_schema())
