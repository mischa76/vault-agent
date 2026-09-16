"""WP42 — a link's relation resolved by more than its name, keyless (spec §5).

The helper's two tiers in isolation, on the WP41 miniatures. The guard next door asserts what
the PIPELINE does with a bound relation; this file asserts the binding itself, including the
reason code, because the reason is what the call sites and the replay branch on.
"""
from __future__ import annotations

from typing import Any

from tests.test_wp41_role_columns_guard import (
    bom_payload,
    bom_schema,
    contact_schema,
    run_greenfield,
)
from tests.test_wp42_link_binding_guard import (
    bom_unter_falschem_namen,
    kontakt_unter_falschem_namen,
)
from vault_agent.link_proposal import resolve_fk_target
from vault_agent.rules.dv2_rules import (
    link_relation_offer,
    normalize_identifier,
    resolve_link_relation,
)
from vault_agent.state import DVModel, SourceTable


def binde(link: Any, model: DVModel, schemas: list[SourceTable]) -> tuple[Any, str]:
    """The binding exactly as the three call sites build it (validator.py:844, 865)."""
    declared = {normalize_identifier(t.table): t for t in schemas}
    return resolve_link_relation(
        link, model, schemas,
        lambda _relation, fk: resolve_fk_target(model, fk, declared)[0],
    )


def _ohne_hub(payload: dict[str, Any], hub: str) -> dict[str, Any]:
    for link in payload["links"]:
        link["connected_hubs"] = [
            h for h in link["connected_hubs"]
            if (h if isinstance(h, str) else h["hub"]) != hub
        ]
    return payload


def _ohne_fremdschluessel(schema: list[SourceTable], table: str) -> list[SourceTable]:
    return [
        SourceTable(table=t.table, columns=list(t.column_names), foreign_keys=[])
        if t.table == table else t
        for t in schema
    ]


async def test_a_relation_offers_its_own_hub_and_each_declared_key_with_multiplicity() -> None:
    """The offer is a multiset, which is the whole reason a self-referencing relation binds:
    `BillOfMaterials` declares two keys into `Product` and therefore offers `hub_product` twice."""
    state = await run_greenfield(bom_payload(), bom_schema())
    [relation] = [t for t in state.source_schemas if t.table == "BillOfMaterials"]
    declared = {normalize_identifier(t.table): t for t in state.source_schemas}
    angebot = link_relation_offer(
        relation, state.dv_model,
        lambda fk: resolve_fk_target(state.dv_model, fk, declared)[0],
    )
    assert angebot == {"hub_product": 2, "hub_unit_measure": 1}


async def test_the_name_binds_first_and_the_offer_is_never_consulted() -> None:
    """Tier 1 unchanged, so every binding that held before WP42 holds now — with reason `name`."""
    state = await run_greenfield(bom_payload(), bom_schema())
    [link] = state.dv_model.links
    relation, grund = binde(link, state.dv_model, state.source_schemas)
    assert (relation.table, grund) == ("BillOfMaterials", "name")


async def test_a_unique_offer_binds_where_the_name_misses() -> None:
    """Tier 2: `link_bom` is not `BillOfMaterials` by name, but exactly one relation offers
    `hub_product` twice beside `hub_unit_measure`."""
    state = await run_greenfield(bom_unter_falschem_namen(), bom_schema())
    [link] = state.dv_model.links
    relation, grund = binde(link, state.dv_model, state.source_schemas)
    assert (relation.table, grund) == ("BillOfMaterials", "offer")


async def test_an_offer_may_exceed_what_the_link_takes() -> None:
    """Cover, not equality. `PurchaseOrderHeader` carries Vendor, Employee and ShipMethod; a link
    taking two of them still reads that relation. Here: the link drops `hub_unit_measure`, and
    `BillOfMaterials` — offering it anyway — still binds."""
    state = await run_greenfield(
        _ohne_hub(bom_unter_falschem_namen(), "hub_unit_measure"), bom_schema()
    )
    [link] = state.dv_model.links
    assert [r.hub for r in link.hub_refs] == ["hub_product", "hub_product"]
    relation, grund = binde(link, state.dv_model, state.source_schemas)
    assert (relation.table, grund) == ("BillOfMaterials", "offer")


async def test_multiplicity_is_required_in_the_other_direction() -> None:
    """A relation offering `hub_product` ONCE does not cover a link taking it twice — the case
    the multiset makes visible and a set would silently bind."""
    schema = bom_schema()
    bom = [t for t in schema if t.table == "BillOfMaterials"][0]
    einfach = [t for t in schema if t.table != "BillOfMaterials"]
    einfach.append(SourceTable(
        table="BillOfMaterials", columns=list(bom.column_names),
        foreign_keys=[fk for fk in bom.foreign_keys
                      if fk.columns != ["ComponentID"]],
    ))
    state = await run_greenfield(bom_unter_falschem_namen(), einfach)
    [link] = state.dv_model.links
    assert binde(link, state.dv_model, state.source_schemas) == (None, "none")


async def test_two_fitting_relations_are_ambiguous_and_bind_nothing() -> None:
    """24 of 348 links over six chains fit more than one relation. Picking one would be a guess
    whose failure mode is wrong data, so the reason is `ambiguous` and nothing binds."""
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
    [link] = state.dv_model.links
    assert binde(link, state.dv_model, state.source_schemas) == (None, "ambiguous")


async def test_a_relation_without_declared_keys_offers_nothing() -> None:
    """WP34 inertness carried into the binding: no declared keys, no offer, reason `none`."""
    schema = _ohne_fremdschluessel(bom_schema(), "BillOfMaterials")
    state = await run_greenfield(bom_unter_falschem_namen(), schema)
    [link] = state.dv_model.links
    assert binde(link, state.dv_model, state.source_schemas) == (None, "none")


async def test_the_contact_link_binds_its_relation_by_offer_under_any_name() -> None:
    """The shape the paid chain produced wrong data on: three participations, three declared
    keys, a name that matches nothing."""
    state = await run_greenfield(kontakt_unter_falschem_namen(), contact_schema())
    [link] = state.dv_model.links
    relation, grund = binde(link, state.dv_model, state.source_schemas)
    assert (relation.table, grund) == ("BusinessEntityContact", "offer")
