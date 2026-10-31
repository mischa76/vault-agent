"""WP105 — a carried binding is the first tier of a link's relation resolution (C38), and the
inferred-stage count includes refused bindings (C39). Committed red before the change. Keyless.

The fixture is the twenty-third chain's step 4 in miniature: `hub_product` built from `Product`
(step 3), `hub_unit_measure` fed by `UnitMeasure` (step 3) and `ProductVendor` (step 4), the size
link naming `SizeUnitMeasureCode`, bound to `Product` in step 3 and carried; step 4's increment is
`ProductVendor` alone, the one relation its offer can see."""
from __future__ import annotations

from typing import Any

from eval.run import UsageTotals, run_metrics
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.staging_generator import construct_stage_name
from vault_agent.existing_model import stage_bindings
from vault_agent.link_proposal import (
    component_keys,
    link_binding_evidence_flags,
    link_binding_reasons,
    link_source_overrides,
    resolve_fk_target,
)
from vault_agent.rules.dv2_rules import (
    normalize_identifier,
    resolve_link_relation,
    stage_model_name,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Link,
    LinkHubRef,
    PipelineFlag,
    SourceTable,
    VaultAgentState,
)

LINK = "link_product_size_unit_measure"
STAGE = "stg_product_size_unit_measure"
BASE = normalize_identifier("product_size_unit_measure")
BINDING_KINDS = (FlagKind.SOURCE_BINDING, FlagKind.BINDING_REJECTED, FlagKind.LINK_BINDING_EVIDENCE)


def _product_vendor() -> SourceTable:
    return SourceTable(table="ProductVendor", schema="Purchasing", columns=[
        {"name": "ProductID", "type": "int"}, {"name": "BusinessEntityID", "type": "int"},
        {"name": "UnitMeasureCode", "type": "nchar(3)"}, {"name": "StandardPrice", "type": "money"},
    ], foreign_keys=[
        {"columns": ["ProductID"], "references_table": "Product",
         "references_columns": ["ProductID"], "references_schema": "Production"},
        {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
         "references_columns": ["UnitMeasureCode"], "references_schema": "Production"},
        {"columns": ["BusinessEntityID"], "references_table": "Vendor",
         "references_columns": ["BusinessEntityID"], "references_schema": "Purchasing"},
    ])


def _product(*, with_size: bool = True) -> SourceTable:
    # The carried catalogue: columns only, no keys (dump_source_catalogue, WP74).
    columns = [{"name": "ProductID", "type": "int"}, {"name": "Name", "type": "nvarchar(50)"},
               {"name": "WeightUnitMeasureCode", "type": "nchar(3)"}]
    if with_size:
        columns.insert(2, {"name": "SizeUnitMeasureCode", "type": "nchar(3)"})
    return SourceTable(table="Product", schema="Production", columns=columns)


def _unit_measure() -> SourceTable:
    return SourceTable(table="UnitMeasure", schema="Production", columns=[
        {"name": "UnitMeasureCode", "type": "nchar(3)"}, {"name": "Name", "type": "nvarchar(50)"},
    ])


def _link() -> Link:
    return Link(name=LINK, description="Unit of measure in which the product size is expressed.",
                connected_hubs=["hub_product", LinkHubRef(
                    hub="hub_unit_measure", role="size", source_key_column="SizeUnitMeasureCode")])


def _existing() -> DVModel:
    """Step 3's vault: both hubs single-source, the link already built."""
    return DVModel(hubs=[
        Hub(name="hub_product", business_key="ProductID", source_entity="Product",
            description="A product."),
        Hub(name="hub_unit_measure", business_key="UnitMeasureCode", source_entity="UnitMeasure",
            description="A unit of measure."),
    ], links=[_link()], satellites=[])


def _model() -> DVModel:
    """Step 4's merged model: `hub_unit_measure` re-stated with `ProductVendor` as a second feed."""
    model = _existing()
    model.hubs[1].sources = [
        HubSource(source_table="UnitMeasure", business_key_column="UnitMeasureCode"),
        HubSource(source_table="ProductVendor", business_key_column="UnitMeasureCode"),
    ]
    return model


def _carried_bindings() -> dict[str, str]:
    return {STAGE: "Product", "stg_product": "Product", "stg_unit_measure": "UnitMeasure"}


def _state(*, carried: bool = True, size_column: bool = True) -> VaultAgentState:
    return VaultAgentState(
        dv_model=_model(), source_schemas=[_product_vendor()], existing_model=_existing(),
        existing_source="step3", carried_schemas=[_product(with_size=size_column), _unit_measure()],
        carried_bindings=_carried_bindings() if carried else {},
    )


def _resolve(carried: dict[str, str] | None) -> tuple[Any, str]:
    model, increment = _model(), [_product_vendor()]
    declared = {normalize_identifier(t.table): t for t in increment}
    relation, grund = resolve_link_relation(
        model.links[0], model, increment,
        lambda _relation, fk: resolve_fk_target(model, fk, declared)[0],
        expand=lambda fk: component_keys(fk, declared),
        carried_bindings=carried, carried_schemas=[_product(), _unit_measure()],
    )
    return (relation.table if relation is not None else None), grund


# ── §2.1 the carried tier ──────────────────────────────────────────────────────────────────
def test_a_carried_binding_is_the_first_tier_of_the_resolution() -> None:
    assert _resolve(_carried_bindings()) == ("Product", "carried")


def test_without_the_carried_binding_the_increments_offer_still_binds() -> None:
    assert _resolve(None) == ("ProductVendor", "offer")


def test_a_carried_binding_to_an_undeclared_relation_falls_through() -> None:
    assert _resolve({STAGE: "Ghost"}) == ("ProductVendor", "offer")


# ── §2.2 the call sites agree ──────────────────────────────────────────────────────────────
def test_a_carried_resolution_produces_no_override_no_reason_no_decision() -> None:
    state = _state()
    assert BASE not in link_source_overrides(state)
    assert BASE not in link_binding_reasons(state)
    assert [f for f in link_binding_evidence_flags(state) if f.asset == LINK] == []
    # the control: the same step without the carried binding binds the offer, as before WP105
    assert link_source_overrides(_state(carried=False))[BASE] == "ProductVendor"


async def test_the_generator_and_the_rebind_leave_the_stage_on_the_carried_relation() -> None:
    state = await CodeGeneratorAgent().run(_state())
    rebind_staging(state)
    meta = state.artifacts.automatedv_yaml["staging"][STAGE]
    assert meta["source_binding"] == "declared"
    source = str(meta["source_model"])
    assert "Product" in source and "ProductVendor" not in source
    # the named column itself, not WP95's alias onto the vendor's unit
    assert meta["derived_columns"]["SIZE_UNITMEASURECODE"] == "SIZEUNITMEASURECODE"
    assert [f for f in state.flags if f.kind in BINDING_KINDS and f.asset in (STAGE, LINK)] == []
    assert stage_bindings(state.artifacts.automatedv_yaml["staging"])[STAGE] == "Product"


async def test_a_carried_relation_lacking_a_hashed_column_is_refused_not_replaced() -> None:
    state = await CodeGeneratorAgent().run(_state(size_column=False))
    rebind_staging(state)
    meta = state.artifacts.automatedv_yaml["staging"][STAGE]
    assert meta["source_binding"] == "inferred"
    refused = [f for f in state.flags if f.kind == FlagKind.BINDING_REJECTED and f.asset == STAGE]
    assert [f.reason for f in refused] == ["Product"]


# ── §2.3 one stage name rule ───────────────────────────────────────────────────────────────
def test_the_stage_name_rule_in_rules_is_the_generators() -> None:
    for name in (LINK, "hub_product", "sat_product_details", "link_bom"):
        assert stage_model_name(name) == construct_stage_name(name)
    assert stage_model_name(LINK) == STAGE


# ── §2.4 C39 ───────────────────────────────────────────────────────────────────────────────
def test_stage_refs_inferred_counts_refused_stages_and_each_stage_once() -> None:
    state = VaultAgentState()
    state.flags = [
        PipelineFlag(agent="code_generator", message="a", kind=FlagKind.SOURCE_BINDING,
                     asset="stg_a", reason="none"),
        PipelineFlag(agent="code_generator", message="b", kind=FlagKind.BINDING_REJECTED,
                     asset="stg_b", reason="T"),
        PipelineFlag(agent="code_generator", message="b2", kind=FlagKind.BINDING_REJECTED,
                     asset="stg_b", reason="U"),
        PipelineFlag(agent="link_proposer", message="c", kind=FlagKind.LINK_BINDING_EVIDENCE,
                     asset="link_c", reason="key"),
    ]
    assert run_metrics(state, 0.0, UsageTotals())["stage_refs_inferred"] == 2
