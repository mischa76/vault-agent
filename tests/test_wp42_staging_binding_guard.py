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
"""
from __future__ import annotations

from typing import Any

from tests.test_wp41_role_columns_guard import bom_payload, bom_schema, run_greenfield
from tests.test_wp42_link_binding_guard import bom_unter_falschem_namen
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


def _inferred(state: VaultAgentState) -> None:
    assert "from {{ ref('raw_bom') }} t" in state.artifacts.staging_models[_VIEW]
    assert _binding_flags(state) == {"stg_bom"}


async def test_a_renamed_link_stage_reads_its_resolved_relation() -> None:
    """Pinned today: the stage is inferred as `raw_bom` and flagged, though the vault side binds
    `BillOfMaterials`. To flip: the view reads `BillOfMaterials`, and no flag remains."""
    state = await _bis_zum_rebind(bom_unter_falschem_namen(), bom_schema())
    _inferred(state)


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
