"""Tests for the CLI.

write_outputs is tested directly with a hand-built state (no graph, no API key); the CLI
wiring is smoke-tested via Typer's CliRunner.
"""
import re
from pathlib import Path

import pytest
import yaml
from rich.console import Console
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
            staging_models={"stg_customer": "-- stage sql"},
            scaffolding={
                "dbt_project.yml": "name: 'vault_project'\n",
                "packages.yml": "packages: []\n",
            },
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
        "models": 2, "staging": 1, "scaffolding": 2, "adrs": 1, "metadata": 1,
        "contracts": 0, "mappings": 0, "review_items": 0, "report": 1,
    }
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "models" / "raw_vault" / "hub_customer.sql").read_text() == "-- hub sql"
    assert (tmp_path / "models" / "raw_vault" / "sat_customer_details.sql").exists()
    assert (tmp_path / "models" / "staging" / "stg_customer.sql").read_text() == "-- stage sql"
    assert (tmp_path / "dbt_project.yml").read_text() == "name: 'vault_project'\n"
    assert (tmp_path / "packages.yml").exists()

    meta = yaml.safe_load((tmp_path / "metadata" / "automatedv.yml").read_text())
    assert meta["hubs"]["hub_customer"]["src_pk"] == "CUSTOMER_HK"

    adr = (tmp_path / "adrs" / "ADR-0004-data-vault-model-derived-from-requirements.md")
    assert adr.exists()
    assert "ADR-0004" in adr.read_text()


def test_write_outputs_skips_empty_sections(tmp_path: Path) -> None:
    counts = write_outputs(VaultAgentState(), tmp_path)

    assert counts == {
        "models": 0, "staging": 0, "scaffolding": 0, "adrs": 0, "metadata": 0,
        "contracts": 0, "mappings": 0, "review_items": 0, "report": 1,
    }
    # The report is always written, even for an empty run (header + empty-model note).
    assert (tmp_path / "report.html").exists()
    assert not (tmp_path / "mappings.review.yml").exists()
    assert not (tmp_path / "models" / "staging").exists()
    assert not (tmp_path / "dbt_project.yml").exists()
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


def test_parse_map_and_mappings_file_round_trip(tmp_path: Path) -> None:
    from vault_agent.cli import _mappings_from_file, _parse_map, _render_mappings_review
    from vault_agent.state import Proposal, ProposedMapping

    assert _parse_map("partner number=VICTOR_PARTNER.PARTN_NR") == (
        "partner number", "VICTOR_PARTNER.PARTN_NR"
    )
    with pytest.raises(ValueError, match="expected 'concept=TABLE.COLUMN'"):
        _parse_map("no target here")

    mapping = ProposedMapping(
        proposals=[Proposal(concept="partner number", table="VICTOR_PARTNER", column="PARTN_NR")],
        gaps=["claims ratio"],
        unresolved=["customer reference"],
    )
    path = tmp_path / "mappings.review.yml"
    path.write_text(_render_mappings_review(mapping), encoding="utf-8")
    assert _mappings_from_file(path) == {"partner number": "VICTOR_PARTNER.PARTN_NR"}


def test_build_decision_carries_mappings() -> None:
    decision = _build_decision([], accept=False, mappings={"c": "T.COL"})
    assert decision["mappings"] == {"c": "T.COL"}


def test_build_decision_collects_owners() -> None:
    decision = _build_decision(["customer=Data Team <d@x.io>", "account=Risk"], accept=True)
    assert decision == {
        "owners": {
            "customer": {"name": "Data Team", "email": "d@x.io"},
            "account": {"name": "Risk", "email": None},
        },
        "accept": True,
        "mappings": {},
        "mapping_sources": {},
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
    from vault_agent.state import FlagKind, PipelineFlag, ValidationIssue, ValidationReport

    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=True,
            issues=[ValidationIssue(severity="warning", code="W_LINK_REDUNDANT_GRAIN",
                                    construct="link_a, link_b",
                                    message="same unit of work twice")],
        ),
        flags=[
            PipelineFlag(
                agent="data_contract",
                message=f"field VICTOR_PARTNER.'F{n}' has an undetermined type; review",
                kind=FlagKind.UNDETERMINED_TYPE,
                asset=f"VICTOR_PARTNER.F{n}",
            )
            for n in range(39)
        ],
    )
    console = Console(record=True, width=200)
    _print_checkpoint(console, assemble_review_queue(state))
    text = console.export_text()

    assert "39× undetermined field type" in text  # collapsed, not 39 lines
    assert "W_LINK_REDUNDANT_GRAIN" in text  # substantive warning still shown
    assert text.index("W_LINK_REDUNDANT_GRAIN") < text.index("39× undetermined field type")


def test_checkpoint_renderers_share_one_presentation_source() -> None:
    """WP5 §5.1: both renderers (markdown in the orchestrator, rich-console in the CLI)
    cover exactly the same kinds, in the same order, from the shared constants."""
    import typing

    from rich.console import Console

    from vault_agent.agents.orchestrator import (
        KIND_HEADINGS,
        KIND_ORDER,
        HumanReviewQueue,
        ReviewItem,
        ReviewKind,
        render_review_queue_md,
    )
    from vault_agent.cli import _print_checkpoint

    # The shared knowledge covers every ReviewKind exactly once.
    assert set(KIND_ORDER) == set(KIND_HEADINGS) == set(typing.get_args(ReviewKind))
    assert len(KIND_ORDER) == len(set(KIND_ORDER))

    queue = HumanReviewQueue(
        items=[
            ReviewItem(kind=kind, summary=f"item for {kind}")
            for kind in typing.get_args(ReviewKind)
        ]
    )
    md = render_review_queue_md(queue)
    console = Console(record=True, width=200)
    _print_checkpoint(console, queue)
    cli_text = console.export_text()

    md_positions = [md.index(KIND_HEADINGS[kind]) for kind in KIND_ORDER]
    cli_positions = [cli_text.index(KIND_HEADINGS[kind]) for kind in KIND_ORDER]
    assert md_positions == sorted(md_positions)  # every heading present, in KIND_ORDER
    assert cli_positions == sorted(cli_positions)  # same kinds, same order in the CLI


# --- Logging + --debug (WP5 §5.4) ---------------------------------------------------------


def _failing_pipeline_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")

    async def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom-for-debug")

    monkeypatch.setattr("vault_agent.cli._run_pipeline", boom)
    return doc


def test_default_failure_is_one_line_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = _failing_pipeline_doc(tmp_path, monkeypatch)
    result = runner.invoke(app, ["run", str(doc)])
    assert result.exit_code == 1
    assert "Pipeline failed:" in result.output
    assert "boom-for-debug" in result.output
    assert "Traceback" not in result.output  # default output unchanged


def test_debug_flag_enables_debug_logging_and_full_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import logging

    doc = _failing_pipeline_doc(tmp_path, monkeypatch)
    configured: dict[str, object] = {}
    # Recorded instead of executed so the test process's logging stays untouched.
    monkeypatch.setattr(
        "vault_agent.cli.logging.basicConfig", lambda **kw: configured.update(kw)
    )
    result = runner.invoke(app, ["--debug", "run", str(doc)])
    assert result.exit_code != 0
    assert configured.get("level") == logging.DEBUG  # the CLI, not the library, configures
    assert isinstance(result.exception, RuntimeError)  # re-raised: full traceback available
    assert str(result.exception) == "boom-for-debug"


# --- Checkpoint pruning on finalise (WP5 §5.5) --------------------------------------------
# MemorySaver won't do here: pruning is exercised against the real sqlite saver in
# tmp_path, cross-checked by reopening the database.


def _sqlite_stub_agents(*, block_signoff: bool) -> "dict[str, object]":
    from vault_agent.agents.base import BaseAgent
    from vault_agent.agents.orchestrator import HumanCheckpointAgent
    from vault_agent.graph import NODES
    from vault_agent.state import Artifacts, ValidationReport

    class _Stub(BaseAgent):
        def __init__(self, name: str) -> None:
            self.name = name

        async def run(self, state: VaultAgentState) -> VaultAgentState:
            if self.name == "validator":
                state.validation_report = ValidationReport(passed=True, issues=[])
            if self.name == "data_contract" and block_signoff:
                state.artifacts = Artifacts(
                    contracts=[
                        {"name": "customer", "owner": {"name": "TODO: assign", "email": None}}
                    ]
                )
            state.decisions.append({"agent": self.name})
            return state

    agents: dict[str, object] = {name: _Stub(name) for name in NODES}
    agents["human_checkpoint"] = HumanCheckpointAgent()  # the real gate
    return agents


async def _thread_checkpoint_count(out_dir: Path, thread_id: str) -> int:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from vault_agent.cli import _checkpoint_db

    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
        return len([c async for c in saver.alist(config)])


async def test_finalised_run_prunes_its_checkpoint_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_sqlite_stub_agents(block_signoff=False)),  # type: ignore[arg-type]
    )
    _, paused, thread_id = await _run_pipeline(tmp_path / "req.md", tmp_path)

    assert paused is False
    assert await _thread_checkpoint_count(tmp_path, thread_id) == 0  # no rows left behind


async def test_paused_run_keeps_thread_until_resume_finalises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _resume_pipeline, _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_sqlite_stub_agents(block_signoff=True)),  # type: ignore[arg-type]
    )
    _, paused, thread_id = await _run_pipeline(tmp_path / "req.md", tmp_path)

    assert paused is True
    assert await _thread_checkpoint_count(tmp_path, thread_id) > 0  # resumable: thread kept

    state, still_paused = await _resume_pipeline(
        tmp_path,
        thread_id,
        {"owners": {"customer": {"name": "Data Team", "email": "data@x.io"}}, "accept": True},
    )

    assert still_paused is False
    assert state.artifacts.contracts[0]["owner"]["name"] == "Data Team"
    assert await _thread_checkpoint_count(tmp_path, thread_id) == 0  # pruned on finalise


# --- WP12: interactive checkpoint prompt (stage 1.5) --------------------------------------


class _ScriptedPrompter:
    """A keyless, TTY-free stand-in for cli._prompter: returns queued answers in order."""

    def __init__(self, texts: list[str], confirms: list[bool]) -> None:
        self._texts = list(texts)
        self._confirms = list(confirms)
        self.text_calls: list[str] = []

    def text(self, console: object, message: str) -> str:
        self.text_calls.append(message)
        return self._texts.pop(0)

    def confirm(self, console: object, message: str, *, default: bool = False) -> bool:
        return self._confirms.pop(0)


def _paused_owner_state() -> VaultAgentState:
    from vault_agent.state import ValidationReport

    state = VaultAgentState()
    state.validation_report = ValidationReport(passed=True, issues=[])
    state.artifacts = Artifacts(
        contracts=[{"name": "customer", "owner": {"name": "TODO: assign", "email": None}}]
    )
    return state


def test_is_interactive_tristate(monkeypatch: pytest.MonkeyPatch) -> None:
    from vault_agent.cli import _is_interactive

    assert _is_interactive(True) is True     # --interactive forces on (even on non-TTY)
    assert _is_interactive(False) is False   # --no-interactive forces off (even on a TTY)
    monkeypatch.setattr("vault_agent.cli.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("vault_agent.cli.sys.stdout.isatty", lambda: True)
    assert _is_interactive(None) is True     # auto: both TTY
    monkeypatch.setattr("vault_agent.cli.sys.stdout.isatty", lambda: False)
    assert _is_interactive(None) is False    # auto: stdout not a TTY


def test_has_decision_flags() -> None:
    from vault_agent.cli import _has_decision_flags

    assert _has_decision_flags(None, False, None, None) is False
    assert _has_decision_flags(["a=B"], False, None, None) is True
    assert _has_decision_flags(None, True, None, None) is True
    assert _has_decision_flags(None, False, Path("m.yml"), None) is True
    assert _has_decision_flags(None, False, None, ["c=T.C"]) is True


def test_run_paused_non_tty_is_non_interactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-TTY regression: a pausing run prints today's resume instructions and never prompts."""
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    guard = _ScriptedPrompter([], [])  # any call would IndexError → proves no prompt fired
    monkeypatch.setattr("vault_agent.cli._prompter", guard)
    doc = tmp_path / "req.md"
    doc.write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["run", str(doc), "--out", str(tmp_path)])

    assert result.exit_code == 0
    assert "Paused at the human-in-the-loop checkpoint." in result.stdout
    assert guard.text_calls == []                        # no prompt in a non-TTY
    assert (tmp_path / ".vault-agent" / "pending.json").exists()  # checkpoint kept


def test_collect_decision_reprompts_on_invalid_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    from vault_agent.cli import _collect_decision

    # First answer is only an email (no owner name) → _parse_owner rejects it → re-prompt.
    scripted = _ScriptedPrompter(texts=["<e@x.io>", "Data Team <e@x.io>"], confirms=[])
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)
    owners, overrides = _collect_decision(Console(), _paused_owner_state())

    assert owners == ["customer=Data Team <e@x.io>"]      # malformed answer re-prompted
    assert overrides == {}
    assert len(scripted.text_calls) == 2


def test_collect_decision_defers_multi_source_key(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = _ScriptedPrompter(texts=[], confirms=[])  # must NOT prompt for the multi-source key
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)
    from vault_agent.cli import _collect_decision

    state = VaultAgentState(
        source_schemas=[
            SourceTable(table="crm_customer", columns=["customer_id"]),
            SourceTable(table="victor_partner", columns=["customer_id"]),
        ]
    )
    state.mappings.unresolved = ["customer id"]

    owners, overrides = _collect_decision(Console(), state)
    assert owners == [] and overrides == {}
    assert scripted.text_calls == []                      # listed, never prompted


def test_interactive_owner_parity_and_finalize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interactive owner+accept builds the SAME decision as the flag-based resume, and a
    successful resume clears the checkpoint."""
    from vault_agent.cli import _interactive_checkpoint
    from vault_agent.state import ValidationReport

    captured: dict[str, object] = {}

    async def fake_resume(
        out: Path, thread_id: str, decision: dict[str, object], trace: bool = True
    ):
        captured["decision"] = decision
        finalized = VaultAgentState()
        finalized.validation_report = ValidationReport(passed=True, issues=[])
        return finalized, False

    monkeypatch.setattr("vault_agent.cli._resume_pipeline", fake_resume)
    scripted = _ScriptedPrompter(texts=["Data Team <data@x.io>"], confirms=[True])
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)
    _write_pending(tmp_path, "tid", Path("req.md"))

    _interactive_checkpoint(Console(), tmp_path, "tid", _paused_owner_state())

    assert captured["decision"] == _build_decision(
        ["customer=Data Team <data@x.io>"], True, {}, {}
    )
    assert _read_pending(tmp_path) is None                # checkpoint cleared on finalize


def test_interactive_decline_keeps_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Declining the accept gate must never resume or lose the checkpoint (abort safety)."""
    from vault_agent.cli import _interactive_checkpoint

    async def must_not_resume(*a: object, **k: object):  # pragma: no cover - must not run
        raise AssertionError("resume must not be called when the human declines")

    monkeypatch.setattr("vault_agent.cli._resume_pipeline", must_not_resume)
    scripted = _ScriptedPrompter(texts=["Data Team <data@x.io>"], confirms=[False])
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)
    _write_pending(tmp_path, "tid", Path("req.md"))

    _interactive_checkpoint(Console(), tmp_path, "tid", _paused_owner_state())

    assert _read_pending(tmp_path) is not None            # checkpoint survives


async def test_paused_state_loads_from_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flag-less interactive resume reconstructs the paused state from its sqlite checkpoint."""
    from vault_agent.cli import _paused_state, _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    _, paused, thread_id = await _run_pipeline(tmp_path / "req.md", tmp_path)
    assert paused is True

    state = await _paused_state(tmp_path, thread_id)
    assert state.artifacts.contracts[0]["owner"]["name"] == "TODO: assign"


def test_interactive_finalize_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance #1 (keyless via the stub graph): a real paused run is taken to finalized
    entirely through the prompt (owner + accept), against the real resume machinery."""
    import asyncio

    from vault_agent.cli import _interactive_checkpoint, _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    state, paused, thread_id = asyncio.run(_run_pipeline(tmp_path / "req.md", tmp_path))
    assert paused is True
    _write_pending(tmp_path, thread_id, tmp_path / "req.md")

    scripted = _ScriptedPrompter(texts=["Data Team <data@x.io>"], confirms=[True])
    monkeypatch.setattr("vault_agent.cli._prompter", scripted)
    _interactive_checkpoint(Console(), tmp_path, thread_id, state)

    assert _read_pending(tmp_path) is None                          # checkpoint cleared
    remaining = asyncio.run(_thread_checkpoint_count(tmp_path, thread_id))
    assert remaining == 0                                           # thread pruned on finalise


# --- WP15: LLM trace capture --------------------------------------------------------------


def _tracing_stub_agents(*, block_signoff: bool) -> "dict[str, object]":
    """The sqlite stub graph, with the modeler emitting one trace event (an LLM call stand-in).

    The stub agents never call the API, so nothing would reach the recorder otherwise; emitting
    through the same ``llm.emit_trace`` seam the real ForcedToolCaller uses keeps the test
    honest about the wiring under test (registration + path + clearing)."""
    from vault_agent import llm

    agents = _sqlite_stub_agents(block_signoff=block_signoff)

    def instrument(node: str, tool: str) -> None:
        agent = agents[node]
        original = agent.run  # type: ignore[union-attr]

        async def run(state: VaultAgentState) -> VaultAgentState:
            llm.emit_trace(
                llm.TraceEvent(
                    kind="llm_call",
                    tool_name=tool,
                    model="stub-model",
                    system_prompt="SYSTEM",
                    system_prompt_sha=llm.prompt_sha("SYSTEM"),
                    payload={"hubs": []},
                )
            )
            return await original(state)

        agent.run = run  # type: ignore[union-attr, method-assign]

    instrument("dv2_modeler", "emit_dv_model")
    instrument("adr_author", "emit_adr")  # runs only past the checkpoint (the resume case)
    return agents


def _trace_files(out_dir: Path) -> list[Path]:
    return sorted((out_dir / ".vault-agent" / "traces").glob("*.jsonl"))


def test_run_writes_a_grepable_trace_per_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    import json

    from vault_agent import llm
    from vault_agent.cli import _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_tracing_stub_agents(block_signoff=False)),
    )
    _, _, thread_id = asyncio.run(_run_pipeline(tmp_path / "req.md", tmp_path))

    traces = _trace_files(tmp_path)
    assert [path.name for path in traces] == [f"{thread_id}.jsonl"]
    records = [json.loads(line) for line in traces[0].read_text().splitlines()]
    assert [record["tool_name"] for record in records] == ["emit_dv_model", "emit_adr"]
    assert records[0]["payload"] == {"hubs": []}
    assert llm._default_trace_recorder is None  # cleared after the run


def test_no_trace_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from vault_agent.cli import _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_tracing_stub_agents(block_signoff=False)),
    )
    asyncio.run(_run_pipeline(tmp_path / "req.md", tmp_path, trace=False))

    assert not (tmp_path / ".vault-agent" / "traces").exists()


def test_resume_appends_to_the_same_thread_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One HITL run — paused and resumed — must read as ONE transcript (WP15 acceptance #1).
    import asyncio

    from vault_agent.cli import _resume_pipeline, _run_pipeline
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_tracing_stub_agents(block_signoff=True)),
    )
    _, paused, thread_id = asyncio.run(_run_pipeline(tmp_path / "req.md", tmp_path))
    assert paused is True
    lines_after_run = _trace_files(tmp_path)[0].read_text().count("\n")

    asyncio.run(
        _resume_pipeline(tmp_path, thread_id, {"owners": {}, "accept": True})
    )

    traces = _trace_files(tmp_path)
    assert len(traces) == 1 and traces[0].name == f"{thread_id}.jsonl"
    assert traces[0].read_text().count("\n") > lines_after_run  # appended, not truncated


def test_run_and_resume_expose_the_trace_flag() -> None:
    for command in ("run", "resume"):
        result = runner.invoke(
            app, [command, "--help"], env={"COLUMNS": "200", "NO_COLOR": "1"}
        )
        assert result.exit_code == 0
        assert "--no-trace" in re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)


# --- WP20: the write path refuses hostile filename components -----------------------------


def test_write_outputs_refuses_a_hostile_model_name(tmp_path: Path) -> None:
    """report.py treats every state string as hostile; the write path now does too. A name
    with a path separator would write outside out_dir — refuse, never rename."""
    from vault_agent.cli import write_outputs

    out_dir = tmp_path / "out"
    state = VaultAgentState(
        artifacts=Artifacts(dbt_models={"../../hub_customer": "select 1"})
    )
    with pytest.raises(ValueError, match="refusing to write raw-vault model"):
        write_outputs(state, out_dir)
    # nothing escaped the output directory
    assert list(tmp_path.rglob("*.sql")) == []


def test_write_outputs_refuses_a_hostile_contract_asset_name(tmp_path: Path) -> None:
    from vault_agent.cli import write_outputs

    out_dir = tmp_path / "out"
    state = VaultAgentState(
        artifacts=Artifacts(contracts=[{"name": "../escape", "namespace": "source"}])
    )
    with pytest.raises(ValueError, match="refusing to write contract"):
        write_outputs(state, out_dir)
    assert list(tmp_path.rglob("*.contract.yml")) == []


def test_write_outputs_refuses_a_hostile_staging_name(tmp_path: Path) -> None:
    from vault_agent.cli import write_outputs

    state = VaultAgentState(
        artifacts=Artifacts(staging_models={"stg_a\nb": "select 1"})
    )
    with pytest.raises(ValueError, match="refusing to write staging model"):
        write_outputs(state, tmp_path / "out")


# --- WP17: crash recovery -----------------------------------------------------------------
# Nothing here needs an API key: the graph is stubbed, but the checkpointer is the REAL
# AsyncSqliteSaver in tmp_path — crash recovery is exactly about what survives on disk.


def _crashing_stub_agents(
    *, crash_node: str, crashes: dict[str, int], block_signoff: bool = False
) -> "dict[str, object]":
    """Stub agents where ``crash_node`` raises on its FIRST execution only.

    ``crashes`` is the shared counter, so the same agent map can be rebuilt per connection
    (as the CLI does) while the "already crashed once" fact survives — which is what makes a
    resume observably continue rather than repeat the failure."""
    from vault_agent.agents.base import BaseAgent
    from vault_agent.agents.orchestrator import HumanCheckpointAgent
    from vault_agent.graph import NODES
    from vault_agent.state import Artifacts, ValidationReport

    class _Stub(BaseAgent):
        def __init__(self, name: str) -> None:
            self.name = name

        async def run(self, state: VaultAgentState) -> VaultAgentState:
            if self.name == crash_node:
                crashes[self.name] = crashes.get(self.name, 0) + 1
                if crashes[self.name] == 1:
                    raise RuntimeError("credit balance too low")
            if self.name == "code_generator":
                state.artifacts.dbt_models = {"hub_customer": "-- paid for already\n"}
            if self.name == "validator":
                state.validation_report = ValidationReport(passed=True, issues=[])
            if self.name == "data_contract" and block_signoff:
                state.artifacts = Artifacts(
                    contracts=[
                        {"name": "customer", "owner": {"name": "TODO: assign", "email": None}}
                    ]
                )
            state.decisions.append({"agent": self.name})
            return state

    agents: dict[str, object] = {name: _Stub(name) for name in NODES}
    agents["human_checkpoint"] = HumanCheckpointAgent()  # the real gate
    return agents


def _use_crashing_graph(
    monkeypatch: pytest.MonkeyPatch,
    *,
    crash_node: str = "validator",
    block_signoff: bool = False,
) -> dict[str, int]:
    from vault_agent.graph import build_graph

    crashes: dict[str, int] = {}
    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(  # type: ignore[arg-type]
            _crashing_stub_agents(
                crash_node=crash_node, crashes=crashes, block_signoff=block_signoff
            )
        ),
    )
    return crashes


async def _thread_ids(out_dir: Path) -> set[str]:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from vault_agent.cli import _checkpoint_db

    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
        await saver.setup()
        async with saver.conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
            return {str(row[0]) for row in await cursor.fetchall()}


async def test_crash_records_pending_and_writes_artifacts_so_far(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core of WP17: a mid-run failure must not throw away paid-for LLM work."""
    from vault_agent.cli import _read_pending, _run_pipeline

    _use_crashing_graph(monkeypatch)
    with pytest.raises(RuntimeError, match="credit balance too low"):
        await _run_pipeline(tmp_path / "req.md", tmp_path)

    pending = _read_pending(tmp_path)
    assert pending is not None
    assert pending["phase"] == "crashed"
    assert pending["error"] == "RuntimeError: credit balance too low"
    assert pending["input"] == str(tmp_path / "req.md")
    # the code generator's output — completed before the crash — is on disk
    assert (tmp_path / "models" / "raw_vault" / "hub_customer.sql").is_file()
    # and the thread is still there, because that is what resume continues
    assert pending["thread_id"] in await _thread_ids(tmp_path)


async def test_resume_continues_a_crashed_run_to_finalisation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _continue_pipeline, _read_pending, _run_pipeline

    crashes = _use_crashing_graph(monkeypatch)
    with pytest.raises(RuntimeError):
        await _run_pipeline(tmp_path / "req.md", tmp_path)
    pending = _read_pending(tmp_path)
    assert pending is not None
    thread_id = pending["thread_id"]

    # A separate saver connection, exactly like `vault-agent resume` in another process.
    state, paused = await _continue_pipeline(tmp_path, thread_id)

    assert paused is False
    assert crashes["validator"] == 2  # only the failed node re-ran
    agents_run = [d["agent"] for d in state.decisions if "agent" in d]
    assert "adr_author" in agents_run  # the run went all the way through
    assert agents_run.count("code_generator") == 1  # completed nodes were NOT re-executed
    assert await _thread_ids(tmp_path) == set()  # finalised -> thread pruned


async def test_crashed_run_that_reaches_the_checkpoint_pauses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _continue_pipeline, _read_pending, _run_pipeline

    _use_crashing_graph(monkeypatch, block_signoff=True)
    with pytest.raises(RuntimeError):
        await _run_pipeline(tmp_path / "req.md", tmp_path)
    pending = _read_pending(tmp_path)
    assert pending is not None

    _, paused = await _continue_pipeline(tmp_path, pending["thread_id"])

    assert paused is True  # the HITL gate still applies after a crash+continue
    assert pending["thread_id"] in await _thread_ids(tmp_path)


def test_resume_of_a_crashed_run_applies_decision_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Continuation + checkpoint in one command: the crashed run runs on, hits the gate, and
    the given --owner/--accept are applied immediately (capability parity, WP12)."""
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_crashing_graph(monkeypatch, block_signoff=True)
    out = tmp_path / "out"
    crashed = runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])
    assert crashed.exit_code == 1
    assert "Pipeline failed:" in crashed.output
    assert "vault-agent resume" in crashed.output  # the run says how to get the work back
    assert _read_pending(out)["phase"] == "crashed"  # type: ignore[index]

    result = runner.invoke(
        app,
        [
            "resume", "--out", str(out), "--no-interactive",
            "--owner", "customer=Data Team <data@x.io>", "--accept",
        ],
    )

    assert result.exit_code == 0
    assert "Continuing" in result.output and "credit balance too low" in result.output
    assert "run finalized" in result.output
    assert _read_pending(out) is None  # pending cleared on finalisation


def test_resume_of_a_crashed_run_without_flags_prints_instructions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-TTY, no flags: the crashed run is continued and the checkpoint is REPORTED, never
    decided on the human's behalf — they have not seen it yet."""
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_crashing_graph(monkeypatch, block_signoff=True)
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])

    result = runner.invoke(app, ["resume", "--out", str(out), "--no-interactive"])

    assert result.exit_code == 0
    assert "Continuing" in result.output
    assert "Paused at the human-in-the-loop checkpoint" in result.output
    assert "run finalized" not in result.output
    pending = _read_pending(out)
    assert pending is not None and pending["phase"] == "paused"  # crashed -> paused


def test_resume_discard_drops_thread_and_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_crashing_graph(monkeypatch)
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])
    pending = _read_pending(out)
    assert pending is not None

    result = runner.invoke(app, ["resume", "--out", str(out), "--discard"])

    assert result.exit_code == 0
    assert "Discarded" in result.output and "crashed" in result.output
    assert _read_pending(out) is None
    import asyncio as _asyncio

    assert _asyncio.run(_thread_ids(out)) == set()


async def test_recovery_failure_never_masks_the_original_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rescue is best-effort by construction: whatever it hits, the user must still see
    the exception that actually killed the run."""
    from vault_agent import cli

    _use_crashing_graph(monkeypatch)

    async def broken_checkpoint_read(*args: object, **kwargs: object) -> object:
        raise OSError("checkpoint unreadable")

    monkeypatch.setattr(cli, "_state_from_checkpoint", broken_checkpoint_read)
    with pytest.raises(RuntimeError, match="credit balance too low"):
        await cli._run_pipeline(tmp_path / "req.md", tmp_path)

    # the pointer (written before the artifact rescue) still made it
    assert cli._read_pending(tmp_path)["phase"] == "crashed"  # type: ignore[index]


async def test_run_start_prunes_orphan_threads_but_spares_the_pending_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIGKILL-class crashes never reach an except-branch, so their threads linger — the
    unbounded growth WP5 §5.5 fixed, reintroduced through the crash path."""
    from vault_agent.cli import _read_pending, _run_pipeline

    # Two crashed runs in a row: pending.json is single-slot, so the FIRST crashed thread
    # loses its pointer when the second crash overwrites it — exactly how a checkpoint DB
    # would otherwise accumulate dead threads run after run.
    _use_crashing_graph(monkeypatch)
    with pytest.raises(RuntimeError):
        await _run_pipeline(tmp_path / "req.md", tmp_path)
    first_thread = _read_pending(tmp_path)["thread_id"]  # type: ignore[index]

    _use_crashing_graph(monkeypatch)  # fresh crash counter: this run fails too
    with pytest.raises(RuntimeError):
        await _run_pipeline(tmp_path / "req.md", tmp_path)
    second_thread = _read_pending(tmp_path)["thread_id"]  # type: ignore[index]
    assert {first_thread, second_thread} <= await _thread_ids(tmp_path)

    # The next run prunes what pending.json no longer references — and only that.
    _use_crashing_graph(monkeypatch, crash_node="__none__")
    _, _, fresh_thread = await _run_pipeline(tmp_path / "req.md", tmp_path)

    threads = await _thread_ids(tmp_path)
    assert first_thread not in threads  # orphaned by the second crash: pruned
    assert second_thread in threads  # still referenced by pending.json: kept
    assert fresh_thread not in threads  # finalised in this run: pruned as usual


def test_pause_writes_the_paused_phase_and_legacy_pending_still_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: the pause path only gains the phase key, and a pre-WP17 pending.json
    (no phase at all) is still treated as paused."""
    import json as _json

    from vault_agent.cli import _pending_path, _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: __import__(
            "vault_agent.graph", fromlist=["build_graph"]
        ).build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    out = tmp_path / "out"
    paused_run = runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])
    assert paused_run.exit_code == 0
    pending = _read_pending(out)
    assert pending is not None and pending["phase"] == "paused"

    # Rewrite it in the pre-WP17 shape and resume: no phase key reads as paused.
    _pending_path(out).write_text(
        _json.dumps({"thread_id": pending["thread_id"], "input": pending["input"]}),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["resume", "--out", str(out), "--no-interactive",
         "--owner", "customer=Data Team <data@x.io>", "--accept"],
    )

    assert result.exit_code == 0
    assert "Resuming" in result.output and "run finalized" in result.output
    assert _read_pending(out) is None


def test_failure_before_the_checkpointer_promises_no_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure with nothing checkpointed must not advertise `resume` — there would be
    nothing to continue, and the user would waste a command finding that out."""
    doc = _failing_pipeline_doc(tmp_path, monkeypatch)  # _run_pipeline itself is stubbed out
    result = runner.invoke(app, ["run", str(doc), "--out", str(tmp_path / "out")])

    assert result.exit_code == 1
    assert "Pipeline failed:" in result.output
    assert "vault-agent resume" not in result.output


# --- WP21 §2.7: --no-write governs ARTIFACTS; run state is always written -------------------


def test_no_write_pause_still_leaves_a_resumable_run_and_says_what_resume_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: __import__(
            "vault_agent.graph", fromlist=["build_graph"]
        ).build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    out = tmp_path / "out"

    result = runner.invoke(
        app, ["run", str(doc), "--out", str(out), "--no-write", "--no-interactive"]
    )

    assert result.exit_code == 0
    assert "nothing written to disk" in result.output
    assert not (out / "report.html").exists()  # artifacts: none
    assert _read_pending(out) is not None  # run state: written, or this would be unresumable
    assert "--no-write" in result.output.split("Paused at the human-in-the-loop")[1]


def test_resume_no_write_finalises_without_artifacts_but_clears_the_run_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: __import__(
            "vault_agent.graph", fromlist=["build_graph"]
        ).build_graph(_sqlite_stub_agents(block_signoff=True)),
    )
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-write", "--no-interactive"])

    result = runner.invoke(
        app,
        ["resume", "--out", str(out), "--no-interactive", "--no-write",
         "--owner", "customer=Data Team <data@x.io>", "--accept"],
    )

    assert result.exit_code == 0
    assert "nothing written to disk" in result.output
    assert "run finalized" in result.output
    assert not (out / "report.html").exists()  # still no artifacts
    assert _read_pending(out) is None  # but the run state is finished and cleaned up
    import asyncio as _asyncio

    assert _asyncio.run(_thread_ids(out)) == set()


# --- WP25: a failed run is a first-class outcome ------------------------------------------
# Keyless: the graph is stubbed with a permanently-failing validator, but the human
# checkpoint and the ADR author are REAL — the point is what the product reports about
# itself when the model never validates.


def _unvalidatable_stub_agents() -> "dict[str, object]":
    """Stub agents whose validator never passes, mirroring the real modeler's counter.

    ``modeling_attempts`` is what bounds the re-model loop, so the stub modeler has to
    increment it or the graph would loop forever."""
    from vault_agent.agents.adr_author import AdrAuthorAgent
    from vault_agent.agents.base import BaseAgent
    from vault_agent.agents.orchestrator import HumanCheckpointAgent
    from vault_agent.graph import NODES
    from vault_agent.state import DVModel, Hub, ValidationIssue, ValidationReport

    class _Stub(BaseAgent):
        def __init__(self, name: str) -> None:
            self.name = name

        async def run(self, state: VaultAgentState) -> VaultAgentState:
            if self.name == "dv2_modeler":
                state.modeling_attempts += 1
                state.dv_model = DVModel(
                    hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="customer", description="The customer.")]
                )
            if self.name == "validator":
                state.validation_report = ValidationReport(
                    passed=False,
                    issues=[ValidationIssue(severity="error", code="E_SAT_DUP_ATTR",
                                            construct="sat_customer_details",
                                            message="duplicate payload column")],
                )
            state.decisions.append({"agent": self.name})
            return state

    agents: dict[str, object] = {name: _Stub(name) for name in NODES}
    agents["human_checkpoint"] = HumanCheckpointAgent()  # the real gate
    agents["adr_author"] = AdrAuthorAgent(today="2026-07-29")  # the real renderer
    return agents


def _use_unvalidatable_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    from vault_agent.graph import build_graph

    monkeypatch.setattr(
        "vault_agent.cli.build_graph",
        lambda: build_graph(_unvalidatable_stub_agents()),  # type: ignore[arg-type]
    )


def test_unvalidatable_run_exits_3_and_stays_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.2 / acceptance #1+#2: exit 3, an explanation, and a checkpoint that EXISTS.

    Before WP25 this exact run exited 0 while review-queue.md said "requires sign-off" and
    `resume` answered "No unfinished run found"."""
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_unvalidatable_graph(monkeypatch)
    out = tmp_path / "out"

    result = runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])

    assert result.exit_code == 3
    assert "The model did not validate" in result.output
    assert "not for deployment" in result.output
    pending = _read_pending(out)
    assert pending is not None and pending["phase"] == "paused"  # resumable, not a dead end
    assert "requires sign-off" in (out / "review-queue.md").read_text(encoding="utf-8")
    assert list((out / "adrs").glob("*.md")) == []  # nothing documented yet


def test_accepting_an_unvalidatable_model_finalises_but_still_exits_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.3: accepted ≠ validated — the artifacts still carry the known errors."""
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_unvalidatable_graph(monkeypatch)
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])

    result = runner.invoke(
        app, ["resume", "--out", str(out), "--no-interactive", "--accept"]
    )

    assert result.exit_code == 3
    assert "run finalized" in result.output
    assert _read_pending(out) is None
    adr = next((out / "adrs").glob("ADR-*.md")).read_text(encoding="utf-8")
    assert "This model did not pass validation." in adr
    assert "E_SAT_DUP_ATTR (sat_customer_details)" in adr


def test_unvalidatable_run_can_be_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.4: the other half of the human's decision — throw the failed model away."""
    from vault_agent.cli import _read_pending

    doc = tmp_path / "req.md"
    doc.write_text("# requirements", encoding="utf-8")
    _use_unvalidatable_graph(monkeypatch)
    out = tmp_path / "out"
    runner.invoke(app, ["run", str(doc), "--out", str(out), "--no-interactive"])

    result = runner.invoke(app, ["resume", "--out", str(out), "--discard"])

    assert result.exit_code == 0  # discarding is a decision, not a failure
    assert "Discarded" in result.output
    assert _read_pending(out) is None
    import asyncio as _asyncio

    assert _asyncio.run(_thread_ids(out)) == set()


def test_source_mapper_does_not_run_on_the_failed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.6: no LLM call is spent mapping a model the human may discard."""
    from vault_agent.cli import _run_pipeline

    _use_unvalidatable_graph(monkeypatch)
    import asyncio as _asyncio

    state, paused, _ = _asyncio.run(_run_pipeline(tmp_path / "req.md", tmp_path / "out"))

    assert paused is True
    agents_run = [d.get("agent") for d in state.decisions]
    assert "source_mapper" not in agents_run
    assert "human_checkpoint" not in agents_run  # interrupted before it recorded a decision


# --- WP27: hygiene (CI parity, corrupt pointer) -------------------------------------------


def test_ci_type_check_is_the_canonical_invocation() -> None:
    """§3.1: cheap drift protection for exactly the defect this was.

    `uv run mypy src` type-checks LESS than the DoD: an explicit path overrides
    pyproject's `files = ["src/vault_agent", "eval"]`, so eval/ — which carries the quality
    gates — was strict-checked locally and not in CI."""
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "run: uv run mypy\n" in workflow
    assert "uv run mypy src" not in workflow


def test_corrupt_pending_is_an_attributable_message_not_a_traceback(tmp_path: Path) -> None:
    """§3.5: pending.json is a documented file users may hand-edit (WP17)."""
    from vault_agent.cli import _checkpoint_dir

    out = tmp_path / "out"
    _checkpoint_dir(out).mkdir(parents=True)
    (_checkpoint_dir(out) / "pending.json").write_text('{"thread_id": "abc', encoding="utf-8")

    result = runner.invoke(app, ["resume", "--out", str(out)])

    assert result.exit_code == 1
    assert "Cannot read the unfinished-run pointer" in result.output
    assert "not valid JSON" in result.output
    assert "Traceback" not in result.output


def test_pending_without_a_thread_id_is_rejected(tmp_path: Path) -> None:
    from vault_agent.cli import _checkpoint_dir

    out = tmp_path / "out"
    _checkpoint_dir(out).mkdir(parents=True)
    (_checkpoint_dir(out) / "pending.json").write_text('{"input": "req.md"}', encoding="utf-8")

    result = runner.invoke(app, ["resume", "--out", str(out)])

    assert result.exit_code == 1
    assert "expected a JSON object with a 'thread_id' key" in result.output


def test_crash_report_and_orphan_pruning_still_swallow_a_corrupt_pointer(
    tmp_path: Path,
) -> None:
    """The already-guarded callers keep treating a broken pointer as "no pointer" — hygiene
    must never be the reason a run cannot start (WP17 §2.4)."""
    import asyncio as _asyncio

    from vault_agent.cli import _checkpoint_dir, _prune_orphan_threads, _report_crashed

    out = tmp_path / "out"
    _checkpoint_dir(out).mkdir(parents=True)
    (_checkpoint_dir(out) / "pending.json").write_text("not json at all", encoding="utf-8")

    _report_crashed(Console(), out)  # no raise, prints nothing actionable
    _asyncio.run(_prune_orphan_threads(None, out, keep="whatever"))  # no raise
