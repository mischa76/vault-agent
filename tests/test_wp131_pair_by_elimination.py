"""WP131 (C67) — a hub taken twice by one link: the participation no role names reads the one
ratified key the role-named ones leave. Written FIRST. The shape is the demo's bill of materials
(2026-11-15): `link_product_assembly_component` takes `hub_product` unqualified (the assembly) and
as `component`; `BillOfMaterials` declares `ProductAssemblyID` and `ComponentID` into `Product`,
both ratified. The pairing gave the component its key and the assembly none, so the stage hashed a
`PRODUCTNUMBER` its relation does not carry and PostgreSQL refused it. Keyless."""
from __future__ import annotations

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.link_proposal import _Grant, _pair_participations, apply_key_licenses
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    KeyLicense,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)

LINK = "link_product_assembly_component"
PRODUCT = SourceTable(table="Product", schema="Production", primary_key=["ProductID"],
                      columns=["ProductID", "ProductNumber", "Name"])
UNIT = SourceTable(table="UnitMeasure", schema="Production", primary_key=["UnitMeasureCode"],
                   columns=["UnitMeasureCode", "Name"])


def _bom(*extra: str, keys: tuple[str, ...] = ("ProductAssemblyID", "ComponentID")) -> SourceTable:
    return SourceTable(
        table="BillOfMaterials", schema="Production", primary_key=["BillOfMaterialsID"],
        columns=["BillOfMaterialsID", *keys, "UnitMeasureCode", "StartDate", "PerAssemblyQty",
                 *extra],
        foreign_keys=[
            *({"columns": [k], "references_table": "Product", "references_columns": ["ProductID"],
               "references_schema": "Production"} for k in keys),
            {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
             "references_columns": ["UnitMeasureCode"], "references_schema": "Production"},
        ],
    )


def _delta(product_key: str = "ProductNumber", roles: tuple[str | None, ...] = (None, "component"),
           ) -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": product_key, "source_entity": "Product",
             "description": "A product."},
            {"name": "hub_unit_measure", "business_key": "UnitMeasureCode",
             "source_entity": "UnitMeasure", "description": "A unit of measure."},
        ],
        "links": [{
            "name": LINK, "description": "A component of an assembly.",
            "connected_hubs": [
                *({"hub": "hub_product", **({"role": r} if r else {})} for r in roles),
                {"hub": "hub_unit_measure"},
            ],
        }],
        "satellites": [{
            "name": "sat_product_assembly_component_details", "parent": LINK,
            "attributes": ["PerAssemblyQty"], "source_table": "BillOfMaterials",
            "description": "Quantity per assembly.",
        }],
    })


def _run(bom: SourceTable, delta: DVModel,
         keys: tuple[str, ...] = ("ProductAssemblyID", "ComponentID"),
         ) -> tuple[DVModel, VaultAgentState]:
    state = VaultAgentState(source_schemas=[PRODUCT, UNIT, bom])
    for column in keys:
        state.link_proposals.licenses.append(KeyLicense(
            source_table="BillOfMaterials", source_column=column, references_table="Product",
            references_column="ProductID", references_schema="Production",
            ratification_status="accepted",
        ))
    return apply_key_licenses(delta, DVModel(), state), state


def _product_refs(model: DVModel) -> dict[str | None, LinkHubRef]:
    [link] = model.links
    return {ref.role: ref for ref in link.hub_refs if ref.hub == "hub_product"}


# ── the rule ────────────────────────────────────────────────────────────────────────────────
def test_the_unqualified_participation_reads_the_key_the_role_left() -> None:
    model, _ = _run(_bom(), _delta())
    refs = _product_refs(model)
    assert refs["component"].key_translation is not None
    assert refs["component"].key_translation.referencing_column == "ComponentID"
    assert refs[None].key_translation is not None, "the assembly got no key (C67)"
    assert refs[None].key_translation.referencing_column == "ProductAssemblyID"


def test_the_links_satellite_reads_both_translations() -> None:
    model, _ = _run(_bom(), _delta())
    [sat] = model.satellites
    assert sat.participation_translations["hub_product:component"].referencing_column == (
        "ComponentID"
    )
    assert sat.participation_translations["hub_product"].referencing_column == "ProductAssemblyID"


def test_each_translation_is_flagged_for_review() -> None:
    _, state = _run(_bom(), _delta())
    assets = sorted(f.asset for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION)
    assert assets == ["BillOfMaterials.ComponentID", "BillOfMaterials.ProductAssemblyID"]


async def test_the_stage_hashes_only_what_its_relation_or_its_view_carries() -> None:
    model, state = _run(_bom(), _delta())
    state.dv_model = model
    await CodeGeneratorAgent().run(state)
    stage = state.artifacts.automatedv_yaml["staging"]["stg_product_assembly_component"]
    projected = {j["projects"]: j["on"] for j in stage["key_translation"]["joins"]}
    assert projected == {
        "PRODUCTNUMBER": "PRODUCTASSEMBLYID = PRODUCTID",
        "COMPONENT_PRODUCTNUMBER": "COMPONENTID = PRODUCTID",
    }
    assert stage["hashed_columns"]["PRODUCT_HK"] == "PRODUCTNUMBER"
    assert stage["hashed_columns"]["COMPONENT_PRODUCT_HK"] == "COMPONENT_PRODUCTNUMBER"


def test_a_hub_on_the_surrogate_gets_the_left_key_as_its_alias() -> None:
    # The same catalogue under a hub keyed on ProductID: nothing to translate, the assembly's
    # column is the hub's key under another name.
    model, _ = _run(_bom(), _delta(product_key="ProductID"))
    refs = _product_refs(model)
    assert refs["component"].source_key_column == "ComponentID"
    assert refs[None].source_key_column == "ProductAssemblyID"
    assert refs[None].key_translation is None


# ── what stays as it was (green before and after) ───────────────────────────────────────────
def test_a_relation_that_carries_the_hubs_key_is_left_alone() -> None:
    # The unqualified participation reads the relation's own column; elimination is for a
    # relation that has nothing else to offer it.
    model, _ = _run(_bom("ProductNumber"), _delta())
    refs = _product_refs(model)
    assert refs[None].key_translation is None and refs[None].source_key_column is None
    assert refs["component"].key_translation is not None


def test_two_keys_left_are_not_guessed() -> None:
    # The role names neither key: both stay unpaired, and two keys for one participation are
    # a question, not an elimination.
    model, _ = _run(_bom(), _delta(roles=(None, "part")))
    refs = _product_refs(model)
    assert refs[None].key_translation is None and refs["part"].key_translation is None


def test_a_role_still_without_its_key_blocks_the_elimination() -> None:
    # Three participations, two ratified keys: `component` takes its own, `substitute` has
    # none — the key left over could be the assembly's or the substitute's. Asked of the
    # pairing itself: a link with a participation no key feeds does not bind to the relation.
    hub = Hub(name="hub_product", business_key="ProductID", source_entity="Product",
              description="A product.")
    refs = [LinkHubRef(hub="hub_product"), LinkHubRef(hub="hub_product", role="component"),
            LinkHubRef(hub="hub_product", role="substitute")]
    grants = [_Grant("BillOfMaterials", c, hub, None, c, False)
              for c in ("ProductAssemblyID", "ComponentID")]
    present = {"BILLOFMATERIALSID", "PRODUCTASSEMBLYID", "COMPONENTID"}
    pairs = _pair_participations(refs, grants, "PRODUCTID", present)
    assert [(ref.role, grant.column) for ref, grant in pairs] == [("component", "ComponentID")]
    # … and without the third participation the same call pairs both.
    pairs = _pair_participations(refs[:2], grants, "PRODUCTID", present)
    assert sorted((ref.role or "", grant.column) for ref, grant in pairs) == [
        ("", "ProductAssemblyID"), ("component", "ComponentID")]


def test_three_keys_two_named_by_roles_leave_the_third_to_the_unqualified() -> None:
    keys = ("ProductAssemblyID", "ComponentID", "SubstituteID")
    model, _ = _run(_bom(keys=keys), _delta(roles=(None, "component", "substitute")), keys=keys)
    refs = _product_refs(model)
    assert refs["substitute"].key_translation is not None
    assert refs[None].key_translation is not None
    assert refs[None].key_translation.referencing_column == "ProductAssemblyID"
