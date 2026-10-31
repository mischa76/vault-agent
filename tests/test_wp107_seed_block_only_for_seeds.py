"""WP107 — `dbt_project.yml` carries a `seeds:` block, and seed column types, only for stages that
read a seed (C10). Committed red before the change. Keyless."""
from __future__ import annotations

from typing import Any

import pytest
import yaml

from tests.test_target_platform import _bank_model, _contract, _typed_contracts
from tests.test_wp95_role_column_from_fk import _DEMO_STATE, _replayed
from vault_agent.agents.staging_generator import build_staging
from vault_agent.state import DVModel, SourceTable


def _model(*entities: str, unbound: frozenset[str] = frozenset()) -> DVModel:
    """One hub and one satellite per entity; a satellite of an `unbound` entity names no
    `source_table`, so its hub's stage is inferred (`raw_<entity>`) — a bound satellite's
    `source_table` is a declared binding (WP7 §7.1), rendered as a bare name even where no
    table of that name is declared, and a bare name is seed-compatible by design."""
    return DVModel.model_validate({
        "hubs": [{"name": f"hub_{e.lower()}", "business_key": f"{e}ID", "source_entity": e,
                  "description": "x"} for e in entities],
        "links": [],
        "satellites": [{"name": f"sat_{e.lower()}_details", "parent": f"hub_{e.lower()}",
                        "attributes": ["Name"], "description": "x",
                        **({} if e in unbound else {"source_table": e})}
                       for e in entities],
    })


def _table(entity: str, *, schema: str | None) -> SourceTable:
    return SourceTable(table=entity, schema=schema, columns=[f"{entity}ID", "Name"])


def _typed(entity: str) -> dict[str, Any]:
    return _contract(entity, [{"name": f"{entity}ID", "data_type": "integer"},
                              {"name": "Name", "data_type": "string"}])


def _project(model: DVModel, schemas: list[SourceTable], contracts: list[dict[str, Any]]) -> str:
    return build_staging(model, schemas, contracts=contracts).scaffolding["dbt_project.yml"]


def test_an_ungrounded_project_keeps_its_seed_block_and_types() -> None:
    doc = yaml.safe_load(_project(_bank_model(), [], _typed_contracts()))
    seeds = doc["seeds"]["vault_project"]
    assert seeds["+quote_columns"] is False
    assert "NATIONAL_CUSTOMER_ID" in seeds["raw_customer"]["+column_types"]


def test_a_grounded_project_reading_sources_only_has_no_seed_block() -> None:
    text = _project(_model("Customer"), [_table("Customer", schema="Sales")], [_typed("Customer")])
    assert "seeds:" not in text and "+column_types" not in text
    assert "source_model:\n  raw: 'Customer'" in build_staging(
        _model("Customer"), [_table("Customer", schema="Sales")]
    ).models["stg_customer"]


def test_a_bare_declared_table_is_seed_compatible_and_keeps_its_types() -> None:
    doc = yaml.safe_load(_project(_model("Customer"), [_table("Customer", schema=None)],
                                  [_typed("Customer")]))
    assert doc["seeds"]["vault_project"]["Customer"]["+column_types"]["CUSTOMERID"] == "bigint"


def test_a_mixed_project_types_only_the_seed_read_relations() -> None:
    doc = yaml.safe_load(_project(
        _model("Customer", "Store"),
        [_table("Customer", schema="Sales"), _table("Store", schema=None)],
        [_typed("Customer"), _typed("Store")],
    ))
    seeds = doc["seeds"]["vault_project"]
    assert "Store" in seeds and "Customer" not in seeds


def test_an_inferred_stage_in_a_grounded_project_is_no_seed() -> None:
    # WP76: the inferred relation sits under the `inferred` source block, not in `seeds/`
    text = _project(_model("Customer", "Product", unbound=frozenset({"Product"})),
                    [_table("Customer", schema="Sales")],
                    [_typed("Customer"), _typed("raw_product")])
    assert "seeds:" not in text
    assert "inferred: 'raw_product'" in build_staging(
        _model("Customer", "Product", unbound=frozenset({"Product"})),
        [_table("Customer", schema="Sales")],
    ).models["stg_product"]


@pytest.mark.skipif(not _DEMO_STATE.is_file(), reason="the shipped demo is not checked out")
async def test_the_owners_sales_step_no_longer_types_seventeen_seeds_it_never_reads() -> None:
    state = await _replayed()
    text = state.artifacts.scaffolding["dbt_project.yml"]
    assert "seeds:" not in text and "+column_types" not in text
