"""WP35 — Databricks as a selectable target platform, keyless.

Three claims, each pinned here:

1. **Inertness.** Without ``--target-platform`` (default ``postgres``) every artifact is what it
   was before WP35 — the existing byte-identity guards (``test_staging_regression``,
   ``test_greenfield_inertness``) carry that; this module adds the explicit "default equals
   postgres" check so the default can never drift away from the baseline unnoticed.
2. **Platform-neutral SQL.** The raw-vault and staging models are identical across platforms;
   only scaffolding differs (seed column types, the README's platform section). Anything that
   makes the SQL differ per platform belongs in AutomateDV's dispatch, not here.
3. **The seed-type dialect.** A contract's abstract types become Databricks' native types —
   ``string`` where VARCHAR would need a length, ``decimal(38,18)`` where the platform default
   ``DECIMAL(10,0)`` would silently truncate fractions (learn.microsoft.com, DECIMAL type).

The Databricks scaffolding is pinned under ``tests/fixtures/staging_databricks_baseline/``,
captured from the generator on 2026-09-11 — a baseline for future changes, not proof of a
warehouse build. Live verification is a separate, recorded activity (docs/log.md).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any, get_args

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from tests.test_agents.test_staging_generator import _bank_model, _contract
from vault_agent.agents.staging_generator import build_staging
from vault_agent.cli import app
from vault_agent.rules.platforms import (
    DATABRICKS_UNSCALED_DECIMAL,
    DEFAULT_TARGET_PLATFORM,
    PLATFORMS,
    SEED_TYPES,
    TargetPlatform,
    platform_profile,
)
from vault_agent.state import VaultAgentState

_ROOT = Path(__file__).parent.parent
_BUILDER_PATH = _ROOT / "demo" / "bank_postgres" / "build_vault_models.py"
_BASELINE = Path(__file__).parent / "fixtures" / "staging_databricks_baseline" / "scaffolding"
_AUTOMATE_DV = _ROOT / "demo" / "bank_postgres" / "dbt_packages" / "automate_dv"


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_vault_models", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _typed_contracts() -> list[dict[str, Any]]:
    """The WP7 §7.3 mapping-table contract, so every abstract seed type appears once."""
    return [_contract("raw_customer", [
        {"name": "national customer ID", "data_type": "string"},
        {"name": "customer count", "data_type": "integer"},
        {"name": "balance", "data_type": "number"},
        {"name": "is active", "data_type": "boolean"},
        {"name": "date of birth", "data_type": "string",
         "semantics": [{"kind": "format", "value": "date"}]},
        {"name": "updated at", "data_type": "string",
         "semantics": [{"kind": "format", "value": "date-time"}]},
        {"name": "mystery", "data_type": "unknown"},
    ])]


def databricks_scaffolding() -> dict[str, str]:
    """The scaffolding the fixture pins: bank model + typed contract, aimed at Databricks."""
    result = build_staging(
        _bank_model(), source_schemas=[], contracts=_typed_contracts(),
        target_platform="databricks",
    )
    return result.scaffolding


# --- 1. inertness -------------------------------------------------------------------------

def test_default_platform_is_postgres_and_identical_to_naming_it() -> None:
    assert DEFAULT_TARGET_PLATFORM == "postgres"
    assert VaultAgentState().target_platform == "postgres"
    implicit = build_staging(_bank_model(), source_schemas=[], contracts=_typed_contracts())
    explicit = build_staging(
        _bank_model(), source_schemas=[], contracts=_typed_contracts(),
        target_platform="postgres",
    )
    assert implicit.models == explicit.models
    assert implicit.scaffolding == explicit.scaffolding


def test_postgres_dialect_is_the_identity() -> None:
    """The Postgres spelling IS the abstract spelling — that is what keeps the WP7 baseline
    byte-identical without a special case in the renderer."""
    assert platform_profile("postgres").seed_types == {t: t for t in SEED_TYPES}


def test_state_rejects_an_unknown_platform() -> None:
    with pytest.raises(ValidationError):
        VaultAgentState(target_platform="oracle")  # type: ignore[arg-type]


# --- 2. platform-neutral SQL --------------------------------------------------------------

async def test_models_are_identical_across_platforms_only_scaffolding_differs() -> None:
    builder = _load_builder()
    model = builder.build_bank_dv_model_with_transfer()
    postgres = await builder.generate_models(model)
    databricks = await builder.generate_models(model, target_platform="databricks")

    assert databricks.artifacts.dbt_models == postgres.artifacts.dbt_models
    assert databricks.artifacts.staging_models == postgres.artifacts.staging_models
    assert databricks.artifacts.automatedv_yaml == postgres.artifacts.automatedv_yaml
    differing = sorted(
        name for name in postgres.artifacts.scaffolding
        if postgres.artifacts.scaffolding[name] != databricks.artifacts.scaffolding[name]
    )
    # No contract in the demo build -> no seed types -> dbt_project.yml is the same too.
    assert differing == ["README.md"]


async def test_agent_reads_the_platform_from_state() -> None:
    builder = _load_builder()
    state = await builder.generate_models(
        builder.build_bank_dv_model(), target_platform="databricks"
    )
    readme = state.artifacts.scaffolding["README.md"]
    assert "## Target platform: databricks" in readme
    assert "dbt-databricks" in readme
    assert "type: databricks" in readme


async def test_rebind_keeps_the_platform() -> None:
    """The source mapper re-renders the scaffolding on rebind (WP9.1 F2); it must not fall
    back to the default platform while doing so."""
    from tests.test_agents.test_source_mapper import _state, _StubProposer
    from vault_agent.agents.source_mapper import SourceMapperAgent

    proposer = _StubProposer({
        "national customer ID": {"decision": "map", "table": "raw_customer",
                                 "column": "NATIONAL_CUSTOMER_ID"},
    })
    state = _state()
    state.target_platform = "databricks"
    out = await SourceMapperAgent(proposer).run(state)
    assert "## Target platform: databricks" in out.artifacts.scaffolding["README.md"]


# --- 3. the seed-type dialect -------------------------------------------------------------

def test_databricks_seed_types_are_native_and_decimal_carries_a_scale() -> None:
    project = databricks_scaffolding()["dbt_project.yml"]
    assert "    raw_customer:\n      +column_types:" in project
    for line in (
        "        NATIONAL_CUSTOMER_ID: string",
        "        CUSTOMER_COUNT: bigint",
        f"        BALANCE: {DATABRICKS_UNSCALED_DECIMAL}",
        "        IS_ACTIVE: boolean",
        "        DATE_OF_BIRTH: date",
        "        UPDATED_AT: timestamp",
        "        LOAD_DATETIME: timestamp",
        "        RECORD_SOURCE: string",
    ):
        assert line in project, line
    assert "MYSTERY" not in project  # unknown stays omitted on every platform
    assert "varchar" not in project  # VARCHAR needs a length on Databricks; STRING is native
    assert re.fullmatch(r"decimal\(38,\d+\)", DATABRICKS_UNSCALED_DECIMAL)


def test_every_platform_translates_every_abstract_seed_type() -> None:
    assert set(get_args(TargetPlatform)) == set(PLATFORMS)
    for profile in PLATFORMS.values():
        assert set(profile.seed_types) == set(SEED_TYPES), profile.name
        assert all(profile.seed_types.values()), profile.name


def test_databricks_scaffolding_matches_the_pinned_baseline() -> None:
    expected = {
        p.relative_to(_BASELINE).as_posix(): p.read_text(encoding="utf-8")
        for p in _BASELINE.rglob("*") if p.is_file()
    }
    actual = databricks_scaffolding()
    assert expected, "fixture missing — run the regeneration helper deliberately"
    for name, text in expected.items():
        assert actual[name] == text, name


@pytest.mark.skip(reason="regeneration helper; run deliberately, see the module docstring")
def test_regenerate_databricks_baseline() -> None:  # pragma: no cover
    for name in ("dbt_project.yml", "README.md"):
        target = _BASELINE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(databricks_scaffolding()[name], encoding="utf-8")


# --- the CLI ------------------------------------------------------------------------------

runner = CliRunner()


def test_cli_run_help_lists_target_platform() -> None:
    result = runner.invoke(app, ["run", "--help"], env={"COLUMNS": "200", "NO_COLOR": "1"})
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--target-platform" in plain
    assert "databricks" in plain


def test_cli_rejects_an_unknown_platform_before_any_model_call(tmp_path: Path) -> None:
    doc = tmp_path / "req.md"
    doc.write_text("# nothing\n", encoding="utf-8")
    result = runner.invoke(app, ["run", str(doc), "--target-platform", "oracle"])
    assert result.exit_code == 2  # typer's usage error — no API key was ever needed


# --- the installed backend ----------------------------------------------------------------

@pytest.mark.skipif(not _AUTOMATE_DV.is_dir(), reason="AutomateDV not installed (dbt deps)")
def test_installed_automate_dv_dispatches_every_called_macro_for_databricks() -> None:
    """Every AutomateDV macro the generated project calls has a Databricks implementation in
    the pinned package (macros/tables/databricks/), and ``stage`` dispatches through the
    adapter with a default that needs no override. The estimate that preceded this WP
    rested on this fact; this makes it a check instead of a memory."""
    # The set is read from the generator's SOURCE, not from one model's output: the bank
    # demo has no multi-active satellite, yet the generator can emit one.
    agents_dir = _ROOT / "src" / "vault_agent" / "agents"
    source = "\n".join(p.read_text(encoding="utf-8") for p in agents_dir.glob("*.py"))
    called = set(re.findall(r"automate_dv\.([a-z_]+)", source))
    assert {"hub", "link", "sat", "eff_sat", "t_link", "ma_sat", "stage"} <= called
    for macro in called - {"stage"}:
        assert (_AUTOMATE_DV / "macros" / "tables" / "databricks" / f"{macro}.sql").is_file(), macro
    stage = (_AUTOMATE_DV / "macros" / "staging" / "stage.sql").read_text(encoding="utf-8")
    assert "adapter.dispatch('stage', 'automate_dv')" in stage
    assert "macro default__stage(" in stage
