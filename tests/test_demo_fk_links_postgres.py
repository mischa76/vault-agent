"""Guardrail test for the FK-derived links demo (demo/fk_links_postgres).

Keeps the runnable WP36/WP37 capture from rotting: it imports the demo's
``build_vault_models.py``, runs the real proposer → applier → merger → generator → validator →
re-bind over the fixed vault and delta, and asserts the two links, their translation views and
the views' data-time tests come out as the 2026-09-13 Postgres build verified them. Keyless."""
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import yaml

_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "fk_links_postgres" / "build_vault_models.py"
)


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fk_links_build_vault_models", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPECTED_RAW_VAULT = {
    "hub_product", "hub_unit_measure", "hub_vendor", "hub_shopping_cart_item",
    "link_shopping_cart_item_product", "link_product_vendor", "sat_vendor_details",
    "hub_employee", "sat_sales_person_details",  # WP38
}
EXPECTED_STAGING = {
    "stg_product", "stg_unit_measure", "stg_vendor", "stg_shopping_cart_item",
    "stg_shopping_cart_item_product", "stg_shopping_cart_item_product_via_product",
    "stg_product_vendor", "stg_product_vendor_via_product_and_vendor",
    "stg_employee", "stg_sales_person_details", "stg_sales_person_details_via_employee",  # WP38
}


async def test_the_two_fk_derived_links_and_their_translations_are_generated() -> None:
    state = await _load_builder().build_state()
    assert set(state.artifacts.dbt_models) == EXPECTED_RAW_VAULT
    assert set(state.artifacts.staging_models) == EXPECTED_STAGING
    # The relationship link stages from ONE view that projects BOTH translated keys.
    stage = state.artifacts.staging_models["stg_product_vendor"]
    assert "source_model: 'stg_product_vendor_via_product_and_vendor'" in stage
    via = state.artifacts.staging_models["stg_product_vendor_via_product_and_vendor"]
    assert via.count("left join") == 2 and "PRODUCTNUMBER" in via and "ACCOUNTNUMBER" in via
    # Every staging model is bound to a declared table: no inferred binding, no gate error.
    assert not [f for f in state.flags if f.kind == "source_binding"]
    assert not [i for i in state.validation_report.issues if i.severity == "error"]


async def test_the_translation_views_ship_parseable_data_time_gates() -> None:
    state = await _load_builder().build_state()
    ymls = {p: c for p, c in state.artifacts.scaffolding.items() if "_via_" in p}
    assert set(ymls) == {
        "models/staging/stg_shopping_cart_item_product_via_product.yml",
        "models/staging/stg_product_vendor_via_product_and_vendor.yml",
        "models/staging/stg_sales_person_details_via_employee.yml",  # WP38
    }
    for content in ymls.values():
        [model] = yaml.safe_load(content)["models"]  # the 2026-09-13 finding: must parse
        tests = [t for c in model["columns"] for t in c["tests"]]
        assert "not_null" in tests
        assert all(t["relationships"]["to"].startswith("ref('") for t in tests
                   if isinstance(t, dict))


async def test_builder_is_idempotent() -> None:
    builder = _load_builder()
    first, second = await builder.build_state(), await builder.build_state()
    assert first.artifacts.dbt_models == second.artifacts.dbt_models
    assert first.artifacts.staging_models == second.artifacts.staging_models
    assert first.artifacts.scaffolding == second.artifacts.scaffolding


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
