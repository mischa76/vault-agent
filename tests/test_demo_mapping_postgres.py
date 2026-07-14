"""Guardrail test for the grounded+ratified mapping demo (demo/mapping_postgres).

Keeps the runnable WP9 §10.8 capture from rotting if the generator/mapper changes: it imports
the demo's ``build_vault_models.py``, runs the *real* CodeGeneratorAgent + ``rebind_staging``
over the fixed bank model — GROUNDED (declared source schema) and RATIFIED (the accepted
business↔source mapping) — and asserts the generated staging binds to the real business-named
source tables with NO inferred-binding flags (the contrast with demo/bank_postgres). Every
staging model is generated; deterministic, no Anthropic API key (WP9 §10.8)."""
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "mapping_postgres" / "build_vault_models.py"
)


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mapping_build_vault_models", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPECTED_MODELS = {
    "hub_customer": "automate_dv.hub",
    "hub_account": "automate_dv.hub",
    "link_account_customer": "automate_dv.link",
    "sat_customer_details": "automate_dv.sat",
    "sat_account_details": "automate_dv.sat",
    "sat_account_customer_eff": "automate_dv.eff_sat",
}

# The declared source tables the generated staging must bind to (grounded+ratified) — NOT the
# inferred raw_* relations of the ungrounded demo.
EXPECTED_BINDINGS = {
    "stg_customer": "customer",
    "stg_account": "account",
    "stg_account_customer": "account_customer",
}


async def test_grounded_staging_binds_to_declared_sources_without_flags() -> None:
    builder = _load_builder()
    state = await builder.build_state()

    # The fixed model produces exactly the six raw-vault constructs.
    assert set(state.artifacts.dbt_models) == set(EXPECTED_MODELS)
    for name, macro in EXPECTED_MODELS.items():
        assert macro in state.artifacts.dbt_models[name], f"{name} should call {macro}"

    # Grounded + ratified: every staging model binds to a DECLARED source table by its real,
    # business-named relation — so there are ZERO inferred-source-binding flags (the whole
    # point vs. the ungrounded demo/bank_postgres, which infers and flags raw_* bindings).
    assert set(state.artifacts.staging_models) == set(EXPECTED_BINDINGS)
    assert state.flags == []
    for stg, source in EXPECTED_BINDINGS.items():
        assert f"source_model: '{source}'" in state.artifacts.staging_models[stg]

    # The ratified hub-key mapping (accepted) is what re-bound the hub staging (WP9 §6).
    accepted = {p.concept: p.table for p in state.mappings.proposals}
    assert accepted == {"national customer ID": "customer", "account number": "account"}


async def test_builder_is_idempotent() -> None:
    """Same fixed model + mapping in → byte-identical SQL out on a second run (WP9 §10.8)."""
    builder = _load_builder()
    first = await builder.build_state()
    second = await builder.build_state()
    assert first.artifacts.dbt_models == second.artifacts.dbt_models
    assert first.artifacts.staging_models == second.artifacts.staging_models


async def test_sources_yml_lists_each_declared_table_once() -> None:
    """The generated sources.yml documents each declared source table exactly once (the
    dedup fix §10.8 surfaced); dbt rejects duplicate source names."""
    builder = _load_builder()
    state = await builder.build_state()
    sources = state.artifacts.scaffolding["models/staging/sources.yml"]
    table_lines = [ln.strip() for ln in sources.splitlines() if ln.strip().startswith("- name:")]
    for table in EXPECTED_BINDINGS.values():
        assert table_lines.count(f"- name: {table}") == 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
