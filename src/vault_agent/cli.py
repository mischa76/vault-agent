"""Command-line entry point for the Vault-Agent pipeline.

``vault-agent run <requirements.md>`` runs the full LangGraph pipeline on a requirements
document and writes the generated AutomateDV/dbt models, the AutomateDV metadata, and the
finalized ADR to an output directory.

The artifact-writing logic lives in ``write_outputs`` (a pure function) so it can be tested
without the graph or an API key; the ``run`` command wires the graph to it.
"""
import asyncio
import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import typer
import yaml
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel
from rich.console import Console
from rich.prompt import Confirm, Prompt

from vault_agent import llm as _llm
from vault_agent import state as _state_module
from vault_agent.agents.orchestrator import (
    KIND_HEADINGS,
    KIND_ORDER,
    HumanReviewQueue,
    aggregate_review_flags,
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.graph import build_graph
from vault_agent.models.contract import ContractOwner
from vault_agent.profiling import load_profiling
from vault_agent.report import build_report
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import (
    ColumnProfile,
    FlagKind,
    ProposedMapping,
    SourceTable,
    VaultAgentState,
)
from vault_agent.trace import JsonlTraceWriter

app = typer.Typer(help="Agentic AI for Data Vault 2.0 automation.", no_args_is_help=True)

# Set by the --debug flag (WP5 §5.4). The CLI is the only place logging is configured —
# library code only emits via module loggers and never touches handlers or levels.
_DEBUG = False


@app.callback()
def main(
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable DEBUG logging (incl. library INFO/DEBUG) and full tracebacks.",
        ),
    ] = False,
) -> None:
    """Agentic AI for Data Vault 2.0 automation."""
    # Also present so `run` stays an explicit subcommand instead of collapsing into the app.
    global _DEBUG
    _DEBUG = debug
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        )


def _adr_filename(adr_text: str) -> str:
    """Derive a stable filename from an ADR's first heading."""
    first_line = adr_text.lstrip().splitlines()[0] if adr_text.strip() else ""
    match = re.match(r"#\s*(ADR-\d+):\s*(.*)", first_line)
    if not match:
        return "ADR.md"
    number, title = match.group(1), match.group(2)
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", title).strip("-").lower()
    return f"{number}-{slug}.md" if slug else f"{number}.md"


def _safe_component(name: str, artifact: str) -> str:
    """Return ``name`` if it is a safe single filename component, else raise (WP20 §2.3).

    Defense in depth at the filesystem boundary: model, staging and contract-asset names are
    LLM-derived, and ``models_dir / f"{name}.sql"`` with a path separator or ``..`` in the
    name writes outside the output directory. ``report.py`` already treats every state string
    as hostile; the write path did not. The validator's ``E_BAD_NAME`` gate should make this
    unreachable for constructs — this is the second lock, and it covers contract asset names,
    which come from declared source tables or LLM entity names and pass no such gate.

    **Refuses, never renames** (house rule: never silently guess) — a sanitised name would
    silently disagree with the dbt ``ref()`` inside the generated SQL."""
    unsafe = (
        not name.strip()
        or "/" in name
        or "\\" in name
        or ".." in name
        or any(ch < " " or ch == "\x7f" for ch in name)
    )
    if unsafe:
        raise ValueError(
            f"refusing to write {artifact} {name!r}: a filename component must not contain a "
            f"path separator, '..', or control characters, and must not be blank; fix the "
            f"name at its source (the writer never renames it)"
        )
    return name


def write_outputs(state: VaultAgentState, out_dir: Path) -> dict[str, int]:
    """Write dbt models, AutomateDV metadata, and ADRs to ``out_dir``; return counts."""
    models_dir = out_dir / "models" / "raw_vault"
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, sql in state.artifacts.dbt_models.items():
        (models_dir / f"{_safe_component(name, 'raw-vault model')}.sql").write_text(
            sql, encoding="utf-8"
        )

    if state.artifacts.staging_models:
        staging_dir = out_dir / "models" / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        for name, sql in state.artifacts.staging_models.items():
            (staging_dir / f"{_safe_component(name, 'staging model')}.sql").write_text(
                sql, encoding="utf-8"
            )

    # Project scaffolding (dbt_project.yml, packages.yml, sources.yml, README.md) —
    # relative paths inside the output dir, so the output is a runnable dbt project.
    for rel_path, content in state.artifacts.scaffolding.items():
        target = out_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    if state.artifacts.automatedv_yaml:
        meta_dir = out_dir / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "automatedv.yml").write_text(
            yaml.safe_dump(state.artifacts.automatedv_yaml, sort_keys=True),
            encoding="utf-8",
        )

    if state.adrs:
        adr_dir = out_dir / "adrs"
        adr_dir.mkdir(parents=True, exist_ok=True)
        for adr in state.adrs:
            filename = _safe_component(_adr_filename(adr), "ADR")
            (adr_dir / filename).write_text(adr, encoding="utf-8")

    if state.artifacts.contracts or state.artifacts.dbt_tests:
        contracts_dir = out_dir / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        for contract in state.artifacts.contracts:
            asset = _safe_component(str(contract.get("name", "contract")), "contract")
            (contracts_dir / f"{asset}.contract.yml").write_text(
                yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
            )
        for asset, tests_yaml in state.artifacts.dbt_tests.items():
            (contracts_dir / f"{_safe_component(asset, 'contract tests')}.tests.yml").write_text(
                tests_yaml, encoding="utf-8"
            )

    mapping = state.mappings
    if mapping.proposals or mapping.gaps or mapping.unresolved:
        (out_dir / "mappings.review.yml").write_text(
            _render_mappings_review(mapping), encoding="utf-8"
        )

    review_queue = assemble_review_queue(state)
    if review_queue.items:
        (out_dir / "review-queue.md").write_text(
            render_review_queue_md(review_queue), encoding="utf-8"
        )

    # WP11: a single self-contained HTML report per run, always written (both the interrupt
    # path — artifacts-so-far — and the finalize path call write_outputs, so a paused run's
    # report shows the pending state and a resumed run overwrites it).
    (out_dir / "report.html").write_text(build_report(state), encoding="utf-8")

    return {
        "models": len(state.artifacts.dbt_models),
        "staging": len(state.artifacts.staging_models),
        "scaffolding": len(state.artifacts.scaffolding),
        "adrs": len(state.adrs),
        "metadata": 1 if state.artifacts.automatedv_yaml else 0,
        "contracts": len(state.artifacts.contracts),
        "mappings": len(mapping.proposals),
        "review_items": len(review_queue.items),
        "report": 1,
    }


def _render_mappings_review(mapping: ProposedMapping) -> str:
    """Render the human-editable business↔source mapping review file (WP9 §5).

    Edit a proposal's ``table``/``column`` (or move an ``unresolved`` concept up into
    ``proposals`` with a source) and resume with ``vault-agent resume --mappings <file>``, or
    override one concept with ``vault-agent resume --map "concept=TABLE.COLUMN"``."""
    doc: dict[str, Any] = {
        "proposals": [
            {
                "concept": p.concept,
                "table": p.table,
                "column": p.column,
                "category": p.category,
                "confidence": round(p.confidence, 3),
                "ratification_status": p.ratification_status,
                "evidence": list(p.evidence),
            }
            for p in mapping.proposals
        ],
        "gaps": list(mapping.gaps),
        "unresolved": list(mapping.unresolved),
    }
    header = (
        "# Business↔source mapping — review & ratify (WP9, ADR-0008).\n"
        "# Edit table/column below, then: vault-agent resume --mappings <this file>\n"
        "# Or override one concept:      vault-agent resume --map \"concept=TABLE.COLUMN\"\n"
        "# gaps have no in-scope source (Business Vault/marts); unresolved need your decision.\n"
    )
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


# Per-output-dir checkpoint storage: the LangGraph SQLite checkpointer (so a paused run can
# be resumed from a separate process) plus a small pointer to the paused thread.
def _checkpoint_dir(out_dir: Path) -> Path:
    return out_dir / ".vault-agent"


def _checkpoint_db(out_dir: Path) -> str:
    return str(_checkpoint_dir(out_dir) / "checkpoints.sqlite")


def _checkpoint_serde() -> JsonPlusSerializer:
    """A serializer that recognises our state models, so a checkpoint round-trips without
    LangGraph's 'unregistered type' deprecation warning and stays future-proof once strict
    msgpack lands. Collected from the state module so new state models are picked up."""
    allowed = {
        obj
        for obj in vars(_state_module).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel
    }
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


def _trace_path(out_dir: Path, thread_id: str) -> Path:
    """Where a run's LLM transcript lands: one jsonl per thread (WP15 §2.3).

    Under ``.vault-agent/`` deliberately — that directory already holds per-run,
    non-deliverable state, and a trace carries raw document/source text (never publish it).
    A resumed run appends to its thread's file, so one HITL run reads as one transcript."""
    return _checkpoint_dir(out_dir) / "traces" / f"{thread_id}.jsonl"


@contextmanager
def _tracing(out_dir: Path, thread_id: str, enabled: bool) -> Iterator[None]:
    """Register the JSONL trace writer as the process-wide recorder for one run.

    Default ON (``--no-trace`` opts out): a trace you have to remember to enable is a trace
    you don't have when you need it. Always cleared afterwards, so an in-process caller (the
    interactive checkpoint, tests) never leaks a recorder into the next run."""
    if not enabled:
        yield
        return
    _llm.set_trace_recorder(JsonlTraceWriter(_trace_path(out_dir, thread_id)))
    try:
        yield
    finally:
        _llm.set_trace_recorder(None)


def _pending_path(out_dir: Path) -> Path:
    return _checkpoint_dir(out_dir) / "pending.json"


def _write_pending(out_dir: Path, thread_id: str, input_doc: Path) -> None:
    path = _pending_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"thread_id": thread_id, "input": str(input_doc)}), encoding="utf-8"
    )


def _read_pending(out_dir: Path) -> dict[str, str] | None:
    path = _pending_path(out_dir)
    if not path.exists():
        return None
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _clear_pending(out_dir: Path) -> None:
    _pending_path(out_dir).unlink(missing_ok=True)


def _state_from_result(result: dict[str, Any]) -> VaultAgentState:
    """Rebuild the state from an ainvoke result, dropping LangGraph's __interrupt__ key."""
    data = {key: value for key, value in result.items() if key != "__interrupt__"}
    return VaultAgentState.model_validate(data)


async def _run_pipeline(
    input_doc: Path,
    out_dir: Path,
    source_schemas: list[SourceTable] | None = None,
    profiling: dict[str, dict[str, ColumnProfile]] | None = None,
    trace: bool = True,
) -> tuple[VaultAgentState, bool, str]:
    """Run the pipeline under a persistent checkpointer. Returns (state, paused, thread_id);
    ``paused`` is true when the human-in-the-loop checkpoint interrupted the run.

    ``source_schemas`` (from ``--source-schema``) activates ADR-0004 grounding; ``profiling``
    (from ``--profiling``, WP9) feeds the business↔source mapper. Empty/``None`` leaves both
    inert. ``trace`` (WP15) writes the run's LLM transcript beside its checkpoint."""
    thread_id = uuid4().hex
    _checkpoint_dir(out_dir).mkdir(parents=True, exist_ok=True)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    with _tracing(out_dir, thread_id, trace):
        async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
            saver.serde = _checkpoint_serde()
            compiled = build_graph().compile(checkpointer=saver)
            result = await compiled.ainvoke(
                # LangGraph's generic ainvoke doesn't infer our pydantic state as StateT;
                # passing VaultAgentState is correct at runtime.
                VaultAgentState(  # type: ignore[arg-type]
                    input_documents=[str(input_doc)],
                    source_schemas=source_schemas or [],
                    profiling=profiling or {},
                ),
                config=config,
            )
            paused = "__interrupt__" in result
            if not paused:
                # Checkpoint pruning (WP5 §5.5): a finalised run's thread is never resumed,
                # so its rows would only grow checkpoints.sqlite unboundedly. Paused runs
                # keep their thread — it is exactly what `vault-agent resume` continues.
                await saver.adelete_thread(thread_id)
    return _state_from_result(result), paused, thread_id


async def _resume_pipeline(
    out_dir: Path, thread_id: str, decision: dict[str, Any], trace: bool = True
) -> tuple[VaultAgentState, bool]:
    """Resume a paused run on the same thread with the human's decision.

    The trace appends to the same thread's jsonl, so a paused+resumed run is one transcript."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    with _tracing(out_dir, thread_id, trace):
        async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
            saver.serde = _checkpoint_serde()
            compiled = build_graph().compile(checkpointer=saver)
            result = await compiled.ainvoke(Command(resume=decision), config=config)
            paused = "__interrupt__" in result
            if not paused:
                # Finalised on resume: prune the thread's checkpoints (WP5 §5.5).
                await saver.adelete_thread(thread_id)
    return _state_from_result(result), paused


def _parse_owner(spec: str) -> tuple[str, dict[str, str | None]]:
    """Parse ``asset=Owner Name <email@host>`` (the ``<email>`` part optional)."""
    asset, sep, rest = spec.partition("=")
    asset, rest = asset.strip(), rest.strip()
    if not sep or not asset or not rest:
        raise ValueError(f"invalid --owner {spec!r}; expected 'asset=Name <email>'")
    email: str | None = None
    match = re.search(r"<([^>]+)>", rest)
    if match:
        email = match.group(1).strip()
        rest = rest[: match.start()].strip()
    if not rest:
        raise ValueError(f"invalid --owner {spec!r}; missing owner name")
    return asset, {"name": rest, "email": email}


def _parse_map(spec: str) -> tuple[str, str]:
    """Parse ``concept=TABLE.COLUMN`` (WP9 --map shortcut)."""
    concept, sep, target = spec.partition("=")
    concept, target = concept.strip(), target.strip()
    if not sep or not concept or "." not in target:
        raise ValueError(f"invalid --map {spec!r}; expected 'concept=TABLE.COLUMN'")
    return concept, target


def _mappings_from_file(path: Path) -> dict[str, str]:
    """Read an edited ``mappings.review.yml`` into ``{concept: 'TABLE.COLUMN'}`` overrides.

    Every proposal that carries a table and column becomes an override — so a human who edits
    a binding, or moves an ``unresolved`` concept up into ``proposals`` with a source, has it
    applied on resume."""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected a mapping with a 'proposals' list")
    overrides: dict[str, str] = {}
    for entry in document.get("proposals", []) or []:
        if not isinstance(entry, dict):
            continue
        concept, table, column = entry.get("concept"), entry.get("table"), entry.get("column")
        if concept and table and column:
            overrides[str(concept)] = f"{table}.{column}"
    return overrides


def _mapping_sources_from_file(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read multi-source key resolutions from an edited ``mappings.review.yml`` (WP10 §2.4).

    A human resolves a multi-candidate business key by adding a ``sources:`` list (each with a
    ``table`` and ``column``) to its proposal entry; on resume each becomes a ``Hub.sources``
    feed. Single-column proposals (no ``sources:``) are handled by :func:`_mappings_from_file`."""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        return {}
    out: dict[str, list[dict[str, str]]] = {}
    for entry in document.get("proposals", []) or []:
        if not isinstance(entry, dict) or not entry.get("concept"):
            continue
        raw = entry.get("sources")
        if not isinstance(raw, list):
            continue
        feeds = [
            {"table": str(s["table"]), "column": str(s["column"])}
            for s in raw
            if isinstance(s, dict) and s.get("table") and s.get("column")
        ]
        if feeds:
            out[str(entry["concept"])] = feeds
    return out


def _build_decision(
    owners: list[str],
    accept: bool,
    mappings: dict[str, str] | None = None,
    mapping_sources: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    parsed: dict[str, dict[str, str | None]] = {}
    for spec in owners:
        asset, owner = _parse_owner(spec)
        parsed[asset] = owner
    return {
        "owners": parsed,
        "accept": accept,
        "mappings": mappings or {},
        "mapping_sources": mapping_sources or {},
    }


# --- WP12: interactive checkpoint prompt (UI-track stage 1.5) -----------------------------
# Ergonomics over the exact same apply_human_decision path the resume flags drive: the prompt
# may only offer what those flags offer (capability-parity rule), and every answer is routed
# through the existing parse/build/resume functions — no decision semantics live here.
# Prompting goes through an injectable module-level seam so the whole flow is keyless-testable
# without a real TTY.


class _Prompter:
    """The default interactive prompter (rich). Injectable: tests replace ``cli._prompter``."""

    def text(self, console: Console, message: str) -> str:
        return Prompt.ask(message, console=console, default="", show_default=False)

    def confirm(self, console: Console, message: str, *, default: bool = False) -> bool:
        return Confirm.ask(message, console=console, default=default)


_prompter: _Prompter = _Prompter()


def _is_interactive(default: bool | None) -> bool:
    """Resolve the ``--interactive/--no-interactive`` tri-state.

    ``True``/``False`` force the mode; ``None`` (the default) is *auto* — interactive only when
    both stdin and stdout are real TTYs, so CI, pipes, and tests keep the non-interactive path
    (which stays byte-identical to the pre-WP12 behaviour)."""
    if default is not None:
        return default
    return sys.stdin.isatty() and sys.stdout.isatty()


def _has_decision_flags(
    owner: list[str] | None, accept: bool, mappings: Path | None, map_: list[str] | None
) -> bool:
    """True when ``resume`` was given any explicit decision — flags win, no prompt is shown."""
    return bool(owner) or accept or mappings is not None or bool(map_)


def _multi_source_unresolved(state: VaultAgentState) -> set[str]:
    """Unresolved concepts that are multi-source business keys (structural — no message text).

    A key whose normalised name is a column in >= 2 declared source tables needs a ``sources:``
    multi-feed resolution, which the prompt cannot express (WP10 §2.4); it is listed with the
    file-based pointer and never prompted (capability-parity rule)."""
    deferred: set[str] = set()
    for concept in state.mappings.unresolved:
        norm = normalize_identifier(concept)
        tables = {
            table.table
            for table in state.source_schemas
            if any(normalize_identifier(col) == norm for col in table.column_names)
        }
        if len(tables) >= 2:
            deferred.add(concept)
    return deferred


def _unresolved_evidence(state: VaultAgentState, concept: str) -> str:
    """The mapper's evidence line for an unresolved concept, from its typed flag (display only)."""
    for flag in state.flags:
        if flag.kind == FlagKind.MAPPING_UNRESOLVED and flag.asset == concept:
            return flag.message
    return ""


def _collect_decision(
    console: Console, state: VaultAgentState
) -> tuple[list[str], dict[str, str]]:
    """Walk the actionable checkpoint items, collecting owner specs and mapping overrides.

    Collects strings only and hands them to the existing parsers — no decision semantics. A
    contract with a placeholder owner (matched on ``ContractOwner.PLACEHOLDER_NAME``, never
    message text) is prompted, as is each single-source unresolved mapping; a malformed answer
    re-prompts, an empty answer skips. Multi-source keys are listed with the file pointer."""
    owners: list[str] = []
    for contract in state.artifacts.contracts:
        owner = contract.get("owner") or {}
        if owner.get("name") != ContractOwner.PLACEHOLDER_NAME:
            continue
        name = str(contract.get("name", ""))
        while True:
            answer = _prompter.text(
                console, f"Owner for contract {name!r} (Name <email>, Enter to skip)"
            ).strip()
            if not answer:
                break
            try:
                _parse_owner(f"{name}={answer}")  # validate via the existing parser
            except ValueError as exc:
                console.print(f"[red]{exc}[/red]")
                continue
            owners.append(f"{name}={answer}")
            break

    overrides: dict[str, str] = {}
    deferred = _multi_source_unresolved(state)
    for concept in state.mappings.unresolved:
        if concept in deferred:
            console.print(
                f"  [yellow]{concept}[/yellow]: multi-source key — resolve via "
                "[cyan]resume --mappings[/cyan] (add a sources: list)"
            )
            continue
        evidence = _unresolved_evidence(state, concept)
        if evidence:
            console.print(f"  {concept}: {evidence}")
        while True:
            answer = _prompter.text(
                console, f"Source for {concept!r} (TABLE.COLUMN, Enter to skip)"
            ).strip()
            if not answer:
                break
            if "." not in answer:
                console.print("[red]expected TABLE.COLUMN[/red]")
                continue
            overrides[concept] = answer
            break
    return owners, overrides


def _interactive_checkpoint(
    console: Console, out: Path, thread_id: str, state: VaultAgentState, trace: bool = True
) -> None:
    """Answer the HITL checkpoint in the terminal, then resume the same thread in-process.

    Collects owners/mappings, shows any (interactively-unfixable) validation errors, and gates
    on an accept confirm that mirrors ``--accept`` exactly. On accept it assembles the decision
    via the existing ``_build_decision`` and resumes via ``_resume_pipeline`` (re-entering the
    loop on the defensive chance of a re-pause). On decline / skip-all / Ctrl-C it leaves the
    checkpoint intact — ``pending.json`` and the checkpointer thread survive and the flag-based
    ``resume`` still works — and prints today's resume instructions."""
    while True:
        try:
            owners, overrides = _collect_decision(console, state)
            for issue in state.validation_report.issues:
                if issue.severity == "error":
                    console.print(f"[red]validation error[/red] {issue.code}: {issue.message}")
            if not _prompter.confirm(console, "Accept and finalize?", default=False):
                _report_paused(console, out)
                return
        except KeyboardInterrupt:
            console.print("\n[yellow]Aborted — checkpoint kept.[/yellow]")
            _report_paused(console, out)
            return

        decision = _build_decision(owners, True, overrides, {})
        state, paused = asyncio.run(_resume_pipeline(out, thread_id, decision, trace))
        _print_summary(console, state)
        counts = write_outputs(state, out)
        _report_written(console, counts, out)
        if not paused:
            _clear_pending(out)
            console.print("\n[bold green]Checkpoint cleared — run finalized.[/bold green]")
            return
        # Re-paused (no node re-interrupts today; defensive): loop with the new state.


async def _paused_state(out: Path, thread_id: str) -> VaultAgentState:
    """Load an interrupted run's state from its checkpoint (for a flag-less interactive resume)."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out)) as saver:
        saver.serde = _checkpoint_serde()
        compiled = build_graph().compile(checkpointer=saver)
        snapshot = await compiled.aget_state(config)
    return VaultAgentState.model_validate(snapshot.values)


def _print_summary(console: Console, state: VaultAgentState) -> None:
    model = state.dv_model
    report = state.validation_report
    verdict = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"
    n_schemas = len(state.source_schemas)
    grounding = f"on ({n_schemas} source table(s))" if n_schemas else "off"
    console.print(
        f"  requirements:  {len(state.requirements)}\n"
        f"  business keys: {len(state.business_keys)}\n"
        f"  grounding:     {grounding}\n"
        f"  model:         {len(model.hubs)} hubs, {len(model.links)} links, "
        f"{len(model.satellites)} satellites\n"
        f"  dbt models:    {len(state.artifacts.dbt_models)} raw vault + "
        f"{len(state.artifacts.staging_models)} staging\n"
        f"  contracts:     {len(state.artifacts.contracts)}\n"
        f"  validation:    {verdict} ({len(report.issues)} issue(s))"
    )
    _print_checkpoint(console, assemble_review_queue(state))


def _print_checkpoint(console: Console, queue: HumanReviewQueue) -> None:
    """Render the human-in-the-loop checkpoint, grouped blocking-first."""
    if not queue.items:
        return
    verdict = (
        "[bold red]requires sign-off[/bold red]"
        if queue.requires_signoff
        else "[bold yellow]advisory only[/bold yellow]"
    )
    console.print(
        f"\n[bold]Human-in-the-loop checkpoint[/bold] — {verdict} "
        f"({len(queue.items)} item(s)):"
    )
    grouped = queue.by_kind()
    for kind in KIND_ORDER:
        group = grouped.get(kind)
        if not group:
            continue
        if kind == "review_flag":
            group = aggregate_review_flags(group)
        console.print(f"  [bold]{KIND_HEADINGS[kind]}[/bold]")
        for item in group:
            detail = f" — {item.detail}" if item.detail else ""
            console.print(f"    - {item.summary}{detail}")


def _report_written(console: Console, counts: dict[str, int], out: Path) -> None:
    console.print(
        f"\n[bold]Wrote[/bold] {counts['models']} raw-vault model(s), "
        f"{counts['staging']} staging model(s), {counts['scaffolding']} scaffolding "
        f"file(s), {counts['contracts']} contract(s), {counts['adrs']} ADR(s), "
        f"{counts['metadata']} metadata file(s), {counts['review_items']} review "
        f"item(s), and [cyan]report.html[/cyan] to [cyan]{out}/[/cyan]"
    )


def _report_paused(console: Console, out: Path) -> None:
    console.print(
        "\n[bold yellow]Paused at the human-in-the-loop checkpoint.[/bold yellow] "
        "Assign the contract owner(s) above and resume:\n"
        f"  [cyan]vault-agent resume --out {out} "
        '--owner "<asset>=<Name> <<email>>"[/cyan]\n'
        "  (repeat --owner per asset; add --accept to proceed once owners are set)"
    )


@app.command()
def run(
    input_doc: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, dir_okay=False,
                       help="Requirements document (.md, .txt, .pdf, or .docx)."),
    ],
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Output directory for generated artifacts."),
    ] = Path("output"),
    source_schema: Annotated[
        Path | None,
        typer.Option(
            "--source-schema", "-s", exists=True, dir_okay=False,
            help="Optional declared source schema (YAML/JSON) to ground keys/attributes against.",
        ),
    ] = None,
    profiling: Annotated[
        Path | None,
        typer.Option(
            "--profiling", exists=True, dir_okay=False,
            help="Optional profiling-evidence file (YAML/JSON) for the WP9 source mapper.",
        ),
    ] = None,
    write: Annotated[
        bool, typer.Option("--write/--no-write", help="Write artifacts to disk."),
    ] = True,
    trace: Annotated[
        bool,
        typer.Option(
            "--trace/--no-trace",
            help="Write the run's LLM transcript to .vault-agent/traces/ (default: on).",
        ),
    ] = True,
    interactive: Annotated[
        bool | None,
        typer.Option(
            "--interactive/--no-interactive",
            help="Answer the checkpoint in the terminal (default: auto — on when a TTY).",
        ),
    ] = None,
) -> None:
    """Run the full pipeline on a requirements document and write the artifacts."""
    console = Console()
    console.print(f"[bold]Running Vault-Agent pipeline[/bold] on {input_doc} …\n")
    try:
        schemas = load_source_schemas(source_schema) if source_schema else []
        profiles = load_profiling(profiling) if profiling else {}
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]Could not load an input file:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    try:
        state, paused, thread_id = asyncio.run(
            _run_pipeline(input_doc, out, schemas, profiles, trace)
        )
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
        if _DEBUG:
            raise  # --debug: full traceback instead of the one-line summary
        console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(console, state)

    if write:
        counts = write_outputs(state, out)
        _report_written(console, counts, out)
    else:
        console.print("\n[dim]--no-write: nothing written to disk.[/dim]")

    if paused:
        _write_pending(out, thread_id, input_doc)
        # WP12: answer the checkpoint in-terminal when interactive (needs write, since the
        # in-process resume finalises to disk); otherwise print today's resume instructions.
        if write and _is_interactive(interactive):
            _interactive_checkpoint(console, out, thread_id, state, trace)
        else:
            _report_paused(console, out)
    else:
        _clear_pending(out)


@app.command()
def resume(
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Output directory of the paused run."),
    ] = Path("output"),
    owner: Annotated[
        list[str] | None,
        typer.Option("--owner", help="Assign a contract owner: 'asset=Name <email>'."),
    ] = None,
    accept: Annotated[
        bool, typer.Option("--accept/--no-accept", help="Accept and proceed past the checkpoint."),
    ] = False,
    mappings: Annotated[
        Path | None,
        typer.Option("--mappings", help="Edited mappings.review.yml to ratify (WP9)."),
    ] = None,
    map_: Annotated[
        list[str] | None,
        typer.Option("--map", help="Override one mapping: 'concept=TABLE.COLUMN' (WP9)."),
    ] = None,
    trace: Annotated[
        bool,
        typer.Option(
            "--trace/--no-trace",
            help="Append the resume's LLM transcript to the run's trace (default: on).",
        ),
    ] = True,
    interactive: Annotated[
        bool | None,
        typer.Option(
            "--interactive/--no-interactive",
            help="Answer the checkpoint in the terminal (default: auto — on when a TTY).",
        ),
    ] = None,
) -> None:
    """Resume a run paused at the human-in-the-loop checkpoint (owners and/or mappings)."""
    console = Console()
    pending = _read_pending(out)
    if pending is None:
        console.print(f"[bold red]No paused run found[/bold red] under [cyan]{out}/[/cyan].")
        raise typer.Exit(code=1)

    # WP12: with no decision flags and a TTY, drive the checkpoint interactively — load the
    # paused state from its checkpoint, then prompt + resume in-process. Flags win (no prompt),
    # and a non-TTY keeps today's flag-based path byte-identical.
    if not _has_decision_flags(owner, accept, mappings, map_) and _is_interactive(interactive):
        try:
            state = asyncio.run(_paused_state(out, pending["thread_id"]))
        except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly
            if _DEBUG:
                raise
            console.print(f"[bold red]Resume failed:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"[bold]Resuming[/bold] paused run in [cyan]{out}/[/cyan] (interactive) …\n")
        _print_checkpoint(console, assemble_review_queue(state))
        _interactive_checkpoint(console, out, pending["thread_id"], state, trace)
        return

    try:
        overrides = _mappings_from_file(mappings) if mappings else {}
        for spec in map_ or []:
            concept, target = _parse_map(spec)
            overrides[concept] = target
        multi = _mapping_sources_from_file(mappings) if mappings else {}
        decision = _build_decision(owner or [], accept, overrides, multi)
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]Resuming[/bold] paused run in [cyan]{out}/[/cyan] …\n")
    try:
        state, paused = asyncio.run(
            _resume_pipeline(out, pending["thread_id"], decision, trace)
        )
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
        if _DEBUG:
            raise  # --debug: full traceback instead of the one-line summary
        console.print(f"[bold red]Resume failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(console, state)
    counts = write_outputs(state, out)
    _report_written(console, counts, out)

    if paused:
        _report_paused(console, out)
    else:
        _clear_pending(out)
        console.print("\n[bold green]Checkpoint cleared — run finalized.[/bold green]")


if __name__ == "__main__":
    app()
