"""Guardrail test for the bank Durchstich builder (demo/bank_postgres).

Keeps the runnable demo from rotting if the code generator changes: it imports the demo's
``build_vault_models.py``, runs the *real* CodeGeneratorAgent over the fixed bank model to a
temp dir, and asserts the six expected raw-vault models are produced with the right
AutomateDV macros. Deterministic — no Anthropic API key (spec §5)."""
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "bank_postgres" / "build_vault_models.py"
)


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_vault_models", _BUILDER_PATH)
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


async def test_builder_emits_six_models_from_the_real_generator(tmp_path: Path) -> None:
    builder = _load_builder()
    state = await builder.generate_models(builder.build_bank_dv_model())

    # No generator errors/flags for this fixed, hand-checked model.
    assert state.errors == []
    assert set(state.artifacts.dbt_models) == set(EXPECTED_MODELS)

    written = builder.write_models(state, tmp_path)
    assert len(written) == len(EXPECTED_MODELS)

    for name, macro in EXPECTED_MODELS.items():
        sql = (tmp_path / f"{name}.sql").read_text(encoding="utf-8")
        assert macro in sql, f"{name} should call {macro}"
        assert "materialized='incremental'" in sql


async def test_builder_is_idempotent(tmp_path: Path) -> None:
    """Same fixed model in → byte-identical SQL out on a second run (spec §5)."""
    builder = _load_builder()
    first = await builder.generate_models(builder.build_bank_dv_model())
    second = await builder.generate_models(builder.build_bank_dv_model())
    assert first.artifacts.dbt_models == second.artifacts.dbt_models


def test_eff_sat_declares_a_driving_key() -> None:
    """The effectivity satellite's link must carry a driving key, else the generator would
    flag it for human review instead of emitting eff_sat (spec §3)."""
    builder = _load_builder()
    model = builder.build_bank_dv_model()
    link = next(link for link in model.links if link.name == "link_account_customer")
    assert link.driving_key == ["hub_account"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
