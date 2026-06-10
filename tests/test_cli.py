"""Tests for the CLI.

write_outputs is tested directly with a hand-built state (no graph, no API key); the CLI
wiring is smoke-tested via Typer's CliRunner.
"""
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vault_agent.cli import _adr_filename, app, write_outputs
from vault_agent.state import Artifacts, VaultAgentState

runner = CliRunner()


def _state_with_artifacts() -> VaultAgentState:
    return VaultAgentState(
        artifacts=Artifacts(
            dbt_models={"hub_customer": "-- hub sql", "sat_customer_details": "-- sat sql"},
            automatedv_yaml={"hubs": {"hub_customer": {"src_pk": "CUSTOMER_HK"}}},
        ),
        adrs=["# ADR-0004: Data Vault model derived from requirements\n\n**Status:** Proposed"],
    )


def test_adr_filename_from_heading() -> None:
    assert _adr_filename("# ADR-0004: Data Vault model derived from requirements") == (
        "ADR-0004-data-vault-model-derived-from-requirements.md"
    )
    assert _adr_filename("no heading here") == "ADR.md"


def test_write_outputs_creates_files(tmp_path: Path) -> None:
    counts = write_outputs(_state_with_artifacts(), tmp_path)

    assert counts == {"models": 2, "adrs": 1, "metadata": 1}
    assert (tmp_path / "models" / "hub_customer.sql").read_text() == "-- hub sql"
    assert (tmp_path / "models" / "sat_customer_details.sql").exists()

    meta = yaml.safe_load((tmp_path / "metadata" / "automatedv.yml").read_text())
    assert meta["hubs"]["hub_customer"]["src_pk"] == "CUSTOMER_HK"

    adr = (tmp_path / "adrs" / "ADR-0004-data-vault-model-derived-from-requirements.md")
    assert adr.exists()
    assert "ADR-0004" in adr.read_text()


def test_write_outputs_skips_empty_sections(tmp_path: Path) -> None:
    counts = write_outputs(VaultAgentState(), tmp_path)

    assert counts == {"models": 0, "adrs": 0, "metadata": 0}
    assert not (tmp_path / "metadata").exists()
    assert not (tmp_path / "adrs").exists()


def test_cli_help_lists_run_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_cli_run_requires_existing_file() -> None:
    result = runner.invoke(app, ["run", "does/not/exist.md"])
    assert result.exit_code != 0
