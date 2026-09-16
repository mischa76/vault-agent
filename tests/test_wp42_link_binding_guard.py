"""WP42 guard, committed BEFORE the capability (spec §4).

The shape the paid chain of 2026-09-16 produced: the modeler builds the bill of materials as
`link_bom` from `BillOfMaterials`, taking `hub_product` twice under the roles `assembly` and
`component`. WP41's pairing never sees it, because a link is bound to its relation by its
CONSTRUCT NAME and `bom` is not `BillOfMaterials`.

* ``test_a_link_whose_name_misses_its_relation_is_not_repaired`` — FLIPPED by WP42.
* ``test_the_wrong_column_gate_is_blind_to_such_a_link`` — FLIPPED by WP42.
* ``test_two_fitting_relations_bind_nothing`` — never flipped.
* ``test_a_relation_that_misses_a_participation_binds_nothing`` — never flipped.
* ``test_nothing_is_built_that_the_modeler_did_not_build`` — never flipped.
"""
from __future__ import annotations

from typing import Any

from tests.test_wp41_role_columns_guard import (
    bom_payload,
    bom_schema,
    contact_payload,
    contact_schema,
    run_greenfield,
)
from vault_agent.state import SourceTable, VaultAgentState


def _umbenennen(payload: dict[str, Any], alt: str, neu: str) -> dict[str, Any]:
    """Denselben Bau unter einem Namen, der die Relation NICHT trifft."""
    for link in payload["links"]:
        if link["name"] == alt:
            link["name"] = neu
    for sat in payload["satellites"]:
        if sat.get("parent") == alt:
            sat["parent"] = neu
    return payload


def bom_unter_falschem_namen() -> dict[str, Any]:
    return _umbenennen(bom_payload(), "link_bill_of_materials", "link_bom")


def kontakt_unter_falschem_namen() -> dict[str, Any]:
    return _umbenennen(contact_payload(person_role=None), "link_business_entity_contact",
                       "link_kontaktrolle")


def _codes(state: VaultAgentState, code: str) -> set[str]:
    return {i.construct for i in state.validation_report.issues if i.code == code}


async def test_a_link_whose_name_misses_its_relation_is_not_repaired() -> None:
    """Flipped by WP42 in its own commit: today no participation is paired, and both roles
    raise W_ROLE_BK_NOT_IN_SOURCE."""
    state = await run_greenfield(bom_unter_falschem_namen(), bom_schema())
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_bom"]
    produkt = [r for r in link.hub_refs if r.hub == "hub_product"]
    assert all(r.key_translation is None and r.source_key_column is None for r in produkt)
    assert _codes(state, "W_ROLE_BK_NOT_IN_SOURCE") == {"link_bom"}


async def test_the_wrong_column_gate_is_blind_to_such_a_link() -> None:
    """Flipped by WP42: the unqualified person is hashed from the organisation's column, but
    the gate never looks, because the link's name binds no relation."""
    state = await run_greenfield(kontakt_unter_falschem_namen(), contact_schema())
    assert _codes(state, "E_LINK_KEY_WRONG_COLUMN") == set()


async def test_two_fitting_relations_bind_nothing() -> None:
    """A second relation offering the same hubs makes the choice ambiguous — never guessed."""
    schema = bom_schema()
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
    state = await run_greenfield(bom_unter_falschem_namen(), [*schema, zwilling])
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_bom"]
    assert all(r.key_translation is None and r.source_key_column is None for r in link.hub_refs)


async def test_a_relation_that_misses_a_participation_binds_nothing() -> None:
    """BillOfMaterials without its unit-measure key no longer offers every participation."""
    schema = bom_schema()
    ohne = [t for t in schema if t.table != "BillOfMaterials"]
    bom = [t for t in schema if t.table == "BillOfMaterials"][0]
    ohne.append(SourceTable(
        table="BillOfMaterials", columns=list(bom.column_names),
        foreign_keys=[fk for fk in bom.foreign_keys if fk.references_table != "UnitMeasure"],
    ))
    state = await run_greenfield(bom_unter_falschem_namen(), ohne)
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_bom"]
    assert all(r.key_translation is None and r.source_key_column is None for r in link.hub_refs)


async def test_nothing_is_built_that_the_modeler_did_not_build() -> None:
    state = await run_greenfield(bom_unter_falschem_namen(), bom_schema())
    assert [lk.name for lk in state.dv_model.links] == ["link_bom"]
