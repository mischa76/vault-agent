"""WP124 (C62) — effectivity satellites: the load-order precondition in the generated README and two
generated dbt tests that fail when it was broken. Committed before the change, failing (spec 2)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

_BUILDER = Path(__file__).parent.parent / "demo" / "bank_postgres" / "build_vault_models.py"


def _builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_vault_models", _BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _bank() -> Any:
    builder = _builder()
    return await builder.generate_models(builder.build_bank_dv_model())


SAT = "sat_account_customer_eff"


# ── T1: one open relationship per driving key ──────────────────────────────────────────────
async def test_a_test_per_effectivity_satellite_for_one_open_relationship() -> None:
    state = await _bank()
    sql = state.artifacts.scaffolding[f"tests/{SAT}__one_open_per_driving_key.sql"]
    assert f"ref('{SAT}')" in sql
    assert "partition by LINK_ACCOUNT_CUSTOMER_HK" in sql
    assert "order by LOAD_DATETIME desc" in sql
    assert "automate_dv.max_datetime()" in sql
    assert "automate_dv.cast_date('EFFECTIVE_TO')" in sql
    assert "group by ACCOUNT_HK" in sql
    assert "having count(*) > 1" in sql


# ── T2: no record ends before it starts ────────────────────────────────────────────────────
async def test_a_test_per_effectivity_satellite_for_end_after_start() -> None:
    state = await _bank()
    sql = state.artifacts.scaffolding[f"tests/{SAT}__end_after_start.sql"]
    assert f"ref('{SAT}')" in sql
    assert "where EFFECTIVE_TO < EFFECTIVE_FROM" in sql


# ── T3: the README states the precondition only when there is an effectivity satellite ─────
async def test_the_readme_states_the_load_order_precondition() -> None:
    state = await _bank()
    assert "load order" in state.artifacts.scaffolding["README.md"]


def test_no_effectivity_satellite_no_tests_and_no_section() -> None:
    from vault_agent.agents.code_generator import effectivity_load_order_tests

    assert effectivity_load_order_tests({"sat_a": {"src_pk": "A_HK", "src_hashdiff": "HD"}}) == {}


# ── T4: a driving key of several columns groups by all of them ─────────────────────────────
def test_a_composite_driving_key_groups_by_every_column() -> None:
    from vault_agent.agents.code_generator import effectivity_load_order_tests

    tests = effectivity_load_order_tests(
        {
            "sat_x_eff": {
                "src_pk": "LINK_X_HK",
                "src_dfk": ["A_HK", "B_HK"],
                "src_sfk": ["C_HK"],
                "src_start_date": "VALID_FROM",
                "src_end_date": "VALID_TO",
                "src_ldts": "LOAD_DATETIME",
            }
        }
    )
    assert "group by A_HK, B_HK" in tests["tests/sat_x_eff__one_open_per_driving_key.sql"]
    assert "where VALID_TO < VALID_FROM" in tests["tests/sat_x_eff__end_after_start.sql"]
