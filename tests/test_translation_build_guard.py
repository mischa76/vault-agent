"""Guards written FIRST, on 2026-09-13, from the first ``dbt build`` of a translated link.

WP36 and WP37 were built keyless on 2026-09-12 and both records say no ``dbt build`` had
compiled a translation model. The first one (demo/fk_links_postgres, local Postgres) failed
before a single model ran, and would have failed again after that:

1. ``stg_*_via_*.yml`` rendered ``to: {{ ref('Vendor') }}`` — Jinja braces unquoted inside
   YAML are a flow mapping with an unhashable key. dbt refuses to PARSE the project, so every
   project with a translated link was unbuildable. dbt's own form is ``to: ref('Vendor')``.
2. A link with TWO translated participations (WP37's ``ProductVendor``: Product AND Vendor)
   got one translation model — the spec held a single ``translation`` slot and the second
   overwrote the first — so its stage hashed ``PRODUCTNUMBER`` from a view that never
   projected it.

Both pins fail on the code of d61cfe7 and are flipped by the fix in its own commit.
"""
from __future__ import annotations

import re

import yaml

from tests.test_wp36_translation import _ratified_state
from tests.test_wp37_relationship import _apply, _state, _vendor_hub
from vault_agent.agents.staging_generator import build_staging
from vault_agent.link_proposal import link_source_overrides
from vault_agent.state import DVModel


def test_the_translation_tests_yml_is_yaml_dbt_can_parse() -> None:
    state = _ratified_state(with_product=True)
    result = build_staging(state.dv_model, state.source_schemas)
    via = next(n for n in result.models if n.endswith("_via_product"))
    yml = yaml.safe_load(result.scaffolding[f"models/staging/{via}.yml"])
    [rel] = [t for c in yml["models"][0]["columns"] for t in c["tests"] if isinstance(t, dict)]
    assert rel["relationships"] == {"to": "source('raw', 'Product')", "field": "PRODUCTID"}


def test_a_link_with_two_translated_participations_projects_both_keys() -> None:
    state = _state()
    _apply(state, DVModel(hubs=[_vendor_hub()]))
    result = build_staging(state.dv_model, state.source_schemas,
                           source_overrides=link_source_overrides(state))
    stage = result.models["stg_product_vendor"]
    match = re.search(r"source_model: '(stg_product_vendor_via_\w+)'", stage)
    assert match is not None
    via = match.group(1)
    sql = result.models[via]
    assert "r1.PRODUCTNUMBER as PRODUCTNUMBER" in sql
    assert "r2.ACCOUNTNUMBER as ACCOUNTNUMBER" in sql
    assert sql.count("left join") == 2
    yml = yaml.safe_load(result.scaffolding[f"models/staging/{via}.yml"])
    columns = {c["name"]: c["tests"] for c in yml["models"][0]["columns"]}
    assert columns["PRODUCTNUMBER"] == ["not_null"]
    assert columns["ACCOUNTNUMBER"] == ["not_null"]
    assert [t["relationships"]["to"] for c in ("PRODUCTID", "BUSINESSENTITYID")
            for t in columns[c] if isinstance(t, dict)] == [
        "ref('Product')",  # not declared in the miniature: the hub's provenance stands for it
        "source('raw', 'Vendor')",  # declared with a schema: the hub's own source() binding
    ]
