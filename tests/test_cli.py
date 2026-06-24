"""Tests for the CLI.

write_outputs is tested directly with a hand-built state (no graph, no API key); the CLI
wiring is smoke-tested via Typer's CliRunner.
"""
import re
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from vault_agent.cli import (
    _adr_filename,
    _build_decision,
    _parse_owner,
    _print_summary,
    _read_pending,
    _write_pending,
    app,
    write_outputs,
)
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import Artifacts, SourceTable, VaultAgentState

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

    assert counts == {
        "models": 2, "adrs": 1, "metadata": 1, "contracts": 0, "review_items": 0,
    }
    assert (tmp_path / "models" / "hub_customer.sql").read_text() == "-- hub sql"
    assert (tmp_path / "models" / "sat_customer_details.sql").exists()

    meta = yaml.safe_load((tmp_path / "metadata" / "automatedv.yml").read_text())
    assert meta["hubs"]["hub_customer"]["src_pk"] == "CUSTOMER_HK"

    adr = (tmp_path / "adrs" / "ADR-0004-data-vault-model-derived-from-requirements.md")
    assert adr.exists()
    assert "ADR-0004" in adr.read_text()


def test_write_outputs_skips_empty_sections(tmp_path: Path) -> None:
    counts = write_outputs(VaultAgentState(), tmp_path)

    assert counts == {
        "models": 0, "adrs": 0, "metadata": 0, "contracts": 0, "review_items": 0,
    }
    assert not (tmp_path / "metadata").exists()
    assert not (tmp_path / "adrs").exists()
    assert not (tmp_path / "contracts").exists()
    assert not (tmp_path / "review-queue.md").exists()


def test_cli_help_lists_run_and_resume_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "resume" in result.stdout


# --- Resume helpers (ADR-0006) -----------------------------------------------------------


def test_parse_owner_with_email() -> None:
    asset, owner = _parse_owner("customer=Data Team <data@x.io>")
    assert asset == "customer"
    assert owner == {"name": "Data Team", "email": "data@x.io"}


def test_parse_owner_without_email() -> None:
    asset, owner = _parse_owner("account=Risk Office")
    assert asset == "account"
    assert owner == {"name": "Risk Office", "email": None}


@pytest.mark.parametrize("spec", ["", "noequals", "=onlyname", "customer="])
def test_parse_owner_rejects_malformed(spec: str) -> None:
    with pytest.raises(ValueError):
        _parse_owner(spec)


def test_build_decision_collects_owners() -> None:
    decision = _build_decision(["customer=Data Team <d@x.io>", "account=Risk"], accept=True)
    assert decision == {
        "owners": {
            "customer": {"name": "Data Team", "email": "d@x.io"},
            "account": {"name": "Risk", "email": None},
        },
        "accept": True,
    }


def test_pending_roundtrip(tmp_path: Path) -> None:
    assert _read_pending(tmp_path) is None
    _write_pending(tmp_path, "thread-abc", Path("req.md"))
    pending = _read_pending(tmp_path)
    assert pending is not None
    assert pending["thread_id"] == "thread-abc"


def test_cli_run_requires_existing_file() -> None:
    result = runner.invoke(app, ["run", "does/not/exist.md"])
    assert result.exit_code != 0


# --- Source-schema input (Phase 1) -------------------------------------------------------


def test_cli_run_help_lists_source_schema_flag() -> None:
    # Rich renders --help with ANSI styling and width-dependent wrapping; CI has no TTY
    # (defaults to 80 cols), which split the option name and failed a raw-substring check.
    # Force a wide, colour-free terminal and strip any residual ANSI before asserting.
    result = runner.invoke(
        app, ["run", "--help"], env={"COLUMNS": "200", "NO_COLOR": "1"}
    )
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--source-schema" in plain


def test_loader_feeds_state_source_schemas(tmp_path: Path) -> None:
    """The loader + state wiring: a declared file lands on VaultAgentState.source_schemas."""
    path = tmp_path / "schema.yml"
    path.write_text(
        "source_schemas:\n"
        "  - table: customer\n"
        "    columns: [national_customer_id, customer_name]\n",
        encoding="utf-8",
    )
    schemas = load_source_schemas(path)
    state = VaultAgentState(input_documents=["doc.md"], source_schemas=schemas)
    assert state.source_schemas == [
        SourceTable(table="customer", columns=["national_customer_id", "customer_name"])
    ]


def test_summary_shows_grounding_on_with_schemas() -> None:
    from rich.console import Console

    console = Console(record=True, width=120)
    state = VaultAgentState(
        source_schemas=[SourceTable(table="customer", columns=["national_customer_id"])]
    )
    _print_summary(console, state)
    assert "grounding:     on (1 source table(s))" in console.export_text()


def test_summary_shows_grounding_off_without_schemas() -> None:
    from rich.console import Console

    console = Console(record=True, width=120)
    _print_summary(console, VaultAgentState())
    assert "grounding:     off" in console.export_text()


# --- Review-queue aggregation in the CLI checkpoint (finding #3) --------------------------


def test_cli_checkpoint_collapses_noise_like_the_md() -> None:
    from rich.console import Console

    from vault_agent.agents.orchestrator import assemble_review_queue
    from vault_agent.cli import _print_checkpoint
    from vault_agent.state import ValidationReport

    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=True,
            issues=[{"severity": "warning", "code": "W_LINK_REDUNDANT_GRAIN",
                     "construct": "link_a, link_b", "message": "same unit of work twice"}],
        ),
        errors=[
            f"data_contract: field VICTOR_PARTNER.'F{n}' has an undetermined type; review"
            for n in range(39)
        ],
    )
    console = Console(record=True, width=200)
    _print_checkpoint(console, assemble_review_queue(state))
    text = console.export_text()

    assert "39× undetermined field type" in text  # collapsed, not 39 lines
    assert "W_LINK_REDUNDANT_GRAIN" in text  # substantive warning still shown
    assert text.index("W_LINK_REDUNDANT_GRAIN") < text.index("39× undetermined field type")
