"""WP129 (C65) — a translation model's name fits the platform's identifier limit whenever the
stage's own name does. Written FIRST. The twenty-sixth chain's
`stg_business_entity_sales_territory_assignment_details` (54 characters) got a 67-character view
and PostgreSQL refused it; WP102's short form adds 13 characters to the stage's name. Keyless."""
from __future__ import annotations

import re

from tests.test_wp102_identifier_limit import _spec as _wp102_spec
from vault_agent.agents.staging_generator import (
    StagingSpec,
    build_staging,
    translation_model_name,
)
from vault_agent.state import DVModel, FlagKind, KeyTranslation, SourceTable

LONG = "business_entity_sales_territory_assignment_details"  # the chain's satellite, 50 characters


def _spec(base: str = LONG, through: str = "SalesTerritory") -> StagingSpec:
    spec = StagingSpec(name=f"stg_{base}", base=base)
    spec.add_translation(
        KeyTranslation(referencing_column="TerritoryID", through_table=through,
                       surrogate_column="TerritoryID", natural_key_column="NAME"),
        f"NAME_VIA_{through.upper()}",
    )
    return spec


def test_wp102s_short_form_is_unchanged_where_it_fits() -> None:
    # Pinned before the change: byte for byte, digest included.
    assert translation_model_name(_wp102_spec(), 63) == "stg_sales_order_customer_via_5_848f61"


def test_a_stage_that_fits_always_gets_a_view_name_that_fits() -> None:
    assert len(_spec().name) == 54
    name = translation_model_name(_spec(), 63)
    assert len(name) <= 63, name
    assert re.fullmatch(r"stg_business_entity_sales_territory_as[a-z_]*_via_1_[0-9a-f]{6}", name)
    assert "__" not in name  # the head does not end in an underscore
    assert name == translation_model_name(_spec(), 63)  # deterministic


def test_two_stages_that_share_a_head_do_not_share_a_view() -> None:
    one = translation_model_name(_spec(LONG + "_one"), 63)
    two = translation_model_name(_spec(LONG + "_two"), 63)
    assert one != two and len(one) <= 63 and len(two) <= 63


def test_one_stage_through_another_table_gets_another_view() -> None:
    other = translation_model_name(_spec(through="Region"), 63)
    assert translation_model_name(_spec(), 63) != other


def test_the_built_project_names_the_view_within_the_limit_and_flags_nothing() -> None:
    tables = [
        SourceTable(table="SalesTerritory", schema="Sales", columns=["TerritoryID", "Name"]),
        SourceTable(
            table="SalesTerritoryHistory", schema="Sales",
            columns=["BusinessEntityID", "TerritoryID", "StartDate"],
            foreign_keys=[{"columns": ["TerritoryID"], "references_table": "SalesTerritory",
                           "references_columns": ["TerritoryID"], "references_schema": "Sales"}],
        ),
    ]
    model = DVModel.model_validate({
        "hubs": [
            {"name": "hub_business_entity", "business_key": "BusinessEntityID",
             "source_entity": "SalesTerritoryHistory", "description": "b"},
            {"name": "hub_sales_territory", "business_key": "Name",
             "source_entity": "SalesTerritory", "description": "t"},
        ],
        "links": [{
            "name": f"link_{LONG}", "description": "l",
            "connected_hubs": [
                {"hub": "hub_business_entity"},
                {"hub": "hub_sales_territory",
                 "key_translation": {"referencing_column": "TerritoryID",
                                     "through_table": "SalesTerritory", "through_schema": "Sales",
                                     "surrogate_column": "TerritoryID",
                                     "natural_key_column": "NAME"}},
            ],
        }],
        "satellites": [],
    })
    result = build_staging(model, tables, source_overrides={LONG.upper(): "SalesTerritoryHistory"},
                           target_platform="postgres")
    [view] = [n for n in result.models if "_via_" in n]
    assert len(view) <= 63, view
    assert f"source_model: '{view}'" in result.models[f"stg_{LONG}"]
    assert f"models/staging/{view}.yml" in result.scaffolding
    assert not [f for f in result.flags if f.kind == FlagKind.GENERATION_GAP]
