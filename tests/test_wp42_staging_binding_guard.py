"""WP42 staging-binding guard, committed BEFORE the change (spec §6, decided 2026-09-17).

WP42 binds a renamed link's VAULT to its relation — the key-license repair and both link gates
find `BillOfMaterials` for `link_bom` through the offer tier. Its STAGE does not: staging finds a
link's table by name (`bind_sources`) or through `link_source_overrides`, which knows only ratified
relationship tables and proposals. So `stg_bom` is inferred as `raw_bom`, flagged, and its
translation view selects from a relation no seed provides — `dbt build` cannot be green. The demo
rename of 2026-09-16 showed exactly that and was reverted (`docs/log.md`, WP42 entry).

Each test mirrors the pipeline to the source mapper's re-bind: modeler (stub), generator,
validator, then `rebind_staging`.

* ``test_a_renamed_link_stage_reads_its_resolved_relation`` — FLIPPED by the change.
* ``test_an_ambiguous_link_stage_stays_inferred_and_flagged`` — never flipped.
* ``test_a_link_stage_missing_a_participation_stays_inferred_and_flagged`` — never flipped.
* ``test_a_name_bound_link_needs_no_override`` — never flipped.
* ``test_a_stage_shared_with_a_hub_is_not_repointed`` — never flipped. Added with the change, not
  before it: the replay over six chains found two links sharing a hub's stage base, and an offer
  override there would replace the hub's mapped binding. It holds at cd523e9 as well.
* ``test_the_next_run_keeps_a_renamed_link_bound`` — FLIPPED; pinned at da87176 as a defect of
  dcb708b, which exempted the extended vault's links: staging is re-derived from model and schema on
  every run, so the exemption let a brownfield run over the SAME vault and schema repoint `stg_bom`
  to `raw_bom`.
"""
from __future__ import annotations

from typing import Any

from tests.test_wp41_role_columns_guard import bom_payload, bom_schema, run_greenfield
from tests.test_wp42_link_binding_guard import bom_unter_falschem_namen
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.link_proposal import link_source_overrides
from vault_agent.state import FlagKind, SourceTable, VaultAgentState

_VIEW = "stg_bom_via_product_and_product"


async def _bis_zum_rebind(payload: dict[str, Any], schemas: list[SourceTable]) -> VaultAgentState:
    state = await run_greenfield(payload, schemas)
    rebind_staging(state)
    return state


def _binding_flags(state: VaultAgentState) -> set[str]:
    return {f.asset or "" for f in state.flags if f.kind == FlagKind.SOURCE_BINDING}


async def test_a_renamed_link_stage_reads_its_resolved_relation() -> None:
    """Flipped by the change (pinned at cd523e9 as: the view selects from `raw_bom`, and
    `stg_bom` carries a SOURCE_BINDING flag). The stage now reads the relation the vault side
    bound — `BillOfMaterials` — through the override path, which raises no flag."""
    state = await _bis_zum_rebind(bom_unter_falschem_namen(), bom_schema())
    assert link_source_overrides(state) == {"BOM": "BillOfMaterials"}
    assert "from {{ ref('BillOfMaterials') }} t" in state.artifacts.staging_models[_VIEW]
    assert _binding_flags(state) == set()


async def test_an_ambiguous_link_stage_stays_inferred_and_flagged() -> None:
    """Two relations offer the link's hubs: the vault binds nothing, so staging must not either."""
    zwilling = SourceTable(
        table="BillOfMaterialsArchive",
        columns=["BillOfMaterialsID", "ProductAssemblyID", "ComponentID", "UnitMeasureCode"],
        foreign_keys=[
            {"columns": ["ProductAssemblyID"], "references_table": "Product",
             "references_columns": ["ProductID"]},
            {"columns": ["ComponentID"], "references_table": "Product",
             "references_columns": ["ProductID"]},
            {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
             "references_columns": ["UnitMeasureCode"]},
        ],
    )
    state = await _bis_zum_rebind(bom_unter_falschem_namen(), [*bom_schema(), zwilling])
    assert "stg_bom" in _binding_flags(state)
    assert "BOM" not in link_source_overrides(state)


async def test_a_link_stage_missing_a_participation_stays_inferred_and_flagged() -> None:
    schema = bom_schema()
    bom = next(t for t in schema if t.table == "BillOfMaterials")
    ohne = [t for t in schema if t.table != "BillOfMaterials"] + [SourceTable(
        table="BillOfMaterials", columns=list(bom.column_names),
        foreign_keys=[fk for fk in bom.foreign_keys if fk.references_table != "UnitMeasure"],
    )]
    state = await _bis_zum_rebind(bom_unter_falschem_namen(), ohne)
    assert "stg_bom" in _binding_flags(state)
    assert "BOM" not in link_source_overrides(state)


async def test_a_name_bound_link_needs_no_override() -> None:
    """The name tier is already staging's own rule; an override for it would only make the
    re-bind fire where it was a no-op, so it must not appear."""
    state = await _bis_zum_rebind(bom_payload(), bom_schema())
    assert link_source_overrides(state) == {}
    assert "from {{ ref('BillOfMaterials') }} t" in (
        state.artifacts.staging_models["stg_bill_of_materials_via_product_and_product"]
    )
    assert _binding_flags(state) == set()


async def test_a_stage_shared_with_a_hub_is_not_repointed() -> None:
    """`hub_bom` and `link_bom` stage into one `stg_bom`. The hub's binding is the source mapper's
    to decide; the link's offer must not overwrite it."""
    payload = bom_unter_falschem_namen()
    payload["hubs"].append({"name": "hub_bom", "business_key": "BillOfMaterialsID",
                            "source_entity": "BillOfMaterialsHeader", "description": "A BOM."})
    state = await _bis_zum_rebind(payload, bom_schema())
    assert "BOM" not in link_source_overrides(state)


async def test_the_next_run_keeps_a_renamed_link_bound() -> None:
    """A brownfield run over the vault the previous run wrote, with the same schema and nothing
    added, must stage `link_bom` as that run did."""
    first = await _bis_zum_rebind(bom_unter_falschem_namen(), bom_schema())
    naechster = VaultAgentState(existing_model=first.dv_model.model_copy(deep=True),
                                source_schemas=bom_schema())
    naechster.dv_model = first.dv_model.model_copy(deep=True)
    naechster = await CodeGeneratorAgent().run(naechster)
    rebind_staging(naechster)
    assert "from {{ ref('BillOfMaterials') }} t" in first.artifacts.staging_models[_VIEW]
    # Flipped by the fix (pinned at da87176 as: the next run reads `raw_bom` and flags `stg_bom`).
    assert naechster.artifacts.staging_models[_VIEW] == first.artifacts.staging_models[_VIEW]
    assert _binding_flags(naechster) == set()
