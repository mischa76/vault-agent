"""WP91 — a PIT per hub as a bounded table (ADR-0016 option B). Committed before the change, failing."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from vault_agent.state import DVModel, FlagKind, VaultAgentState


def _model() -> DVModel:
    return DVModel.model_validate({
        "hubs": [
            {"name": "hub_account", "business_key": "AccountNumber", "source_entity": "Account",
             "description": "a"},
            {"name": "hub_customer", "business_key": "CustomerID", "source_entity": "Customer",
             "description": "c"},
            {"name": "hub_branch", "business_key": "BranchCode", "source_entity": "Branch",
             "description": "b"},
        ],
        "links": [
            {"name": "link_account_customer", "description": "holder",
             "connected_hubs": ["hub_account", "hub_customer"]},
        ],
        "satellites": [
            {"name": "sat_account_details", "parent": "hub_account", "attributes": ["Balance"],
             "description": "d"},
            {"name": "sat_account_status", "parent": "hub_account", "attributes": ["Status"],
             "description": "s"},
            {"name": "sat_account_limits", "parent": "hub_account", "attributes": ["Limit", "ValidFrom"],
             "sat_type": "multi_active", "child_dependent_key": ["ValidFrom"], "description": "l"},
            {"name": "sat_customer_details", "parent": "hub_customer", "attributes": ["Name"],
             "description": "n"},
            {"name": "sat_branch_details", "parent": "hub_branch", "attributes": ["City"],
             "description": "y"},
            {"name": "sat_branch_opening", "parent": "hub_branch", "attributes": ["OpenedOn"],
             "sat_type": "effectivity", "description": "o"},
            {"name": "sat_account_customer_role", "parent": "link_account_customer",
             "attributes": ["Role"], "description": "r"},
            {"name": "sat_account_customer_since", "parent": "link_account_customer",
             "attributes": ["Since"], "description": "w"},
        ],
    })


def _options(**overrides: Any) -> Any:
    from vault_agent.state import BusinessVaultOptions

    base: dict[str, Any] = {"pit": True, "as_of_start": date(2026, 10, 15),
                            "as_of_end": date(2026, 10, 26)}
    base.update(overrides)
    return BusinessVaultOptions(**base)


async def _generated(options: Any = None) -> VaultAgentState:
    from vault_agent.agents.code_generator import CodeGeneratorAgent

    state = VaultAgentState(dv_model=_model())
    if options is not None:
        state.business_vault = options
    return await CodeGeneratorAgent().run(state)


# ── §2 rule 6: options, off by default; a PIT needs its bounds ─────────────────────────────
def test_options_default_off_and_a_pit_requires_both_bounds() -> None:
    from vault_agent.state import BusinessVaultOptions

    assert VaultAgentState().business_vault == BusinessVaultOptions()
    assert BusinessVaultOptions().pit is False
    with pytest.raises(ValidationError):
        BusinessVaultOptions(pit=True)
    with pytest.raises(ValidationError):
        BusinessVaultOptions(pit=True, as_of_start=date(2026, 10, 26), as_of_end=date(2026, 10, 15))
    assert _options().as_of_grain == "day"


# ── §1: eligibility — two or more descriptive satellites of the hub ───────────────────────
def test_hubs_with_two_or_more_descriptive_satellites_get_a_pit() -> None:
    from vault_agent.agents.business_vault_generator import pit_hubs

    eligible = {hub: [s.name for s in sats] for hub, sats in pit_hubs(_model()).items()}
    assert eligible == {
        "hub_account": ["sat_account_details", "sat_account_status", "sat_account_limits"],
    }  # customer: one satellite; branch: one plus an effectivity; the link's are the link's


# ── §2 rules 1 and 3: the rendered PIT ─────────────────────────────────────────────────────
async def test_the_pit_reads_hub_satellites_and_spine_with_automatedv_ghost_values() -> None:
    state = await _generated(_options())
    sql = state.artifacts.business_vault_models["pit_account"]
    assert "{{ config(materialized='table') }}" in sql
    assert "{{ ref('as_of_dates') }}" in sql and "{{ ref('hub_account') }}" in sql
    for sat in ("sat_account_details", "sat_account_status", "sat_account_limits"):
        assert f"{{{{ ref('{sat}') }}}}" in sql
        assert f"as {sat.upper()}_PK" in sql and f"as {sat.upper()}_LDTS" in sql
    assert "automate_dv.binary_ghost(none, var('hash', 'MD5'))" in sql
    assert "automate_dv.date_ghost(date_type='timestamp')" in sql
    assert "max(s.LOAD_DATETIME)" in sql and "s.LOAD_DATETIME <= b.AS_OF_DATE" in sql
    assert "ACCOUNT_HK" in sql  # the hub's hash key as the raw vault names it
    assert "multi-active" in sql  # the header says what a ghost entry of sat_account_limits means


# ── §2 rule 2: the spine ───────────────────────────────────────────────────────────────────
async def test_the_as_of_spine_is_a_date_spine_over_the_bounds() -> None:
    state = await _generated(_options(as_of_grain="month"))
    sql = state.artifacts.business_vault_models["as_of_dates"]
    assert "dbt_utils.date_spine(" in sql
    assert 'datepart="month"' in sql
    assert "cast('2026-10-15' as date)" in sql and "cast('2026-10-26' as date)" in sql
    assert "as AS_OF_DATE" in sql


# ── §2 rules 1–3: scaffolding only changes when PIT is on ─────────────────────────────────
async def test_scaffolding_declares_ghost_records_the_block_and_dbt_utils_only_with_pit() -> None:
    off = (await _generated()).artifacts.scaffolding
    on = (await _generated(_options())).artifacts.scaffolding
    assert "enable_ghost_records" not in off["dbt_project.yml"]
    assert "business_vault" not in off["dbt_project.yml"]
    assert "dbt_utils" not in off["packages.yml"]
    assert "enable_ghost_records: true" in on["dbt_project.yml"]
    assert "business_vault:\n      +materialized: table" in on["dbt_project.yml"]
    assert "dbt-labs/dbt_utils" in on["packages.yml"] and "1.4.1" in on["packages.yml"]


# ── §2 rules 4 and 5: integration, metadata, disclosure ───────────────────────────────────
async def test_the_code_generator_emits_models_metadata_and_one_disclosure_per_pit() -> None:
    from vault_agent.agents.orchestrator import flag_role

    state = await _generated(_options())
    assert set(state.artifacts.business_vault_models) == {"as_of_dates", "pit_account"}
    pit = state.artifacts.automatedv_yaml["pit"]["pit_account"]
    assert pit["source_model"] == "hub_account" and pit["src_pk"] == "ACCOUNT_HK"
    assert pit["as_of_dates_table"] == "as_of_dates"
    assert set(pit["satellites"]) == {"sat_account_details", "sat_account_status",
                                      "sat_account_limits"}
    assert pit["satellites"]["sat_account_status"] == {"pk": "ACCOUNT_HK", "ldts": "LOAD_DATETIME"}
    [flag] = [f for f in state.flags if f.kind == FlagKind.PIT_GENERATED]
    assert flag.asset == "pit_account" and "hub_account" in flag.message
    assert flag_role(flag) == "disclosure"


async def test_without_the_option_nothing_is_emitted() -> None:
    state = await _generated()
    assert state.artifacts.business_vault_models == {}
    assert "pit" not in state.artifacts.automatedv_yaml
    assert not [f for f in state.flags if f.kind == FlagKind.PIT_GENERATED]


async def test_write_outputs_places_pits_under_models_business_vault(tmp_path: Path) -> None:
    from vault_agent.cli import write_outputs

    state = await _generated(_options())
    write_outputs(state, tmp_path)
    assert (tmp_path / "models" / "business_vault" / "pit_account.sql").exists()
    assert (tmp_path / "models" / "business_vault" / "as_of_dates.sql").exists()


# ── CLI and workbench carry the option ─────────────────────────────────────────────────────
def test_the_cli_refuses_pit_without_bounds(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from vault_agent.cli import app

    doc = tmp_path / "req.md"
    doc.write_text("# r\n")
    result = CliRunner().invoke(app, ["run", str(doc), "--out", str(tmp_path / "out"), "--pit"])
    assert result.exit_code != 0
    assert "as-of-start" in result.output and "as-of-end" in result.output


def test_the_workbench_start_body_carries_the_pit_fields() -> None:
    from vault_agent.ui.app import StartRun

    body = StartRun.model_validate({"requirements": "r.md", "pit": True,
                                    "as_of_start": "2026-10-15", "as_of_end": "2026-10-26"})
    assert body.business_vault().pit is True
    assert StartRun.model_validate({"requirements": "r.md"}).business_vault().pit is False
