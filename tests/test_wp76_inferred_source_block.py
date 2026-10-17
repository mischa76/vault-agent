"""WP76 — inferred relations are declared under an `inferred` source block in the target schema
when the project addresses its declared inputs through `source()` (spec §3). Committed before
the change, failing. The fixture is WP74's two-step bank shape with the link left unbound."""
from __future__ import annotations

import yaml

from tests.test_wp74_self_contained_project import STEP1, STEP2, _model1, _model2
from vault_agent.agents.staging_generator import build_staging, unresolved_stage_refs
from vault_agent.rules.dv2_rules import INFERRED_SOURCE_NAME
from vault_agent.state import DVModel, FlagKind, SourceTable


def test_an_unbound_stage_reads_the_inferred_block_and_the_project_resolves() -> None:
    result = build_staging(_model2(), STEP2, existing=_model1(), carried=STEP1)
    link = result.models["stg_account_customer"]
    assert f"source_model:\n  {INFERRED_SOURCE_NAME}: 'raw_account_customer'" in link
    sources = result.scaffolding["models/staging/sources.yml"]
    parsed = yaml.safe_load(sources)
    blocks = {b["name"]: b for b in parsed["sources"]}
    assert blocks[INFERRED_SOURCE_NAME]["schema"] == "{{ target.schema }}"
    assert [t["name"] for t in blocks[INFERRED_SOURCE_NAME]["tables"]] == ["raw_account_customer"]
    assert "schema: Sales" in sources and "schema: Bank" in sources  # the declared blocks stay
    assert unresolved_stage_refs(result.models, sources) == []
    assert [f.asset for f in result.flags if f.kind == FlagKind.SOURCE_BINDING] == [
        "stg_account_customer"
    ]  # still a disclosure: a human provides the relation
    assert result.metadata["stg_account_customer"]["source_binding"] == "inferred"


def test_without_a_declared_block_the_bare_seed_name_stays() -> None:
    located = [SourceTable(table=t.table, columns=t.column_names) for t in STEP2]  # no schema
    result = build_staging(_model2(), located, existing=_model1())
    assert "source_model: 'raw_account_customer'" in result.models["stg_account_customer"]
    sources = result.scaffolding["models/staging/sources.yml"]
    assert f"- name: {INFERRED_SOURCE_NAME}" not in sources  # no block, the seed pattern


# Byte identity of the ungrounded baseline is guarded by
# tests/test_agents/test_staging_regression.py (spec §3.2).


def test_a_translation_view_over_an_inferred_stage_uses_the_block() -> None:
    schema = [
        SourceTable(table="Product", columns=["ProductID", "ProductNumber"], schema="Production"),
        SourceTable(table="Document", columns=["DocumentNode", "ProductID"], schema="Production"),
    ]
    model = DVModel.model_validate({
        "hubs": [
            {"name": "hub_product", "business_key": "ProductNumber", "source_entity": "Product",
             "description": "p"},
            {"name": "hub_document", "business_key": "DocumentNode",
             "source_entity": "Document", "description": "d"},
        ],
        "links": [{
            "name": "link_document_product",
            "connected_hubs": [
                "hub_document",
                {"hub": "hub_product",
                 "key_translation": {"through_table": "Product", "surrogate_column": "ProductID",
                                     "natural_key_column": "ProductNumber",
                                     "referencing_column": "ProductID"}},
            ],
            "description": "l",
        }],
        "satellites": [],
    })
    result = build_staging(model, schema)
    view = result.models["stg_document_product_via_product"]
    assert f"source('{INFERRED_SOURCE_NAME}', 'raw_document_product')" in view
    assert "ref('raw_document_product')" not in view
    assert unresolved_stage_refs(
        result.models, result.scaffolding["models/staging/sources.yml"]
    ) == []
