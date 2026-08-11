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
from typing import Annotated, Any, cast
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
from vault_agent.agents.entity_resolver import pending_resolution_decisions
from vault_agent.agents.orchestrator import (
    KIND_HEADINGS,
    KIND_ORDER,
    HumanReviewQueue,
    aggregate_review_flags,
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.existing_model import DV_MODEL_FILENAME, load_existing_model
from vault_agent.extension_diff import DIFF_FILENAME, ExtensionDiff, render_extension_diff_md
from vault_agent.graph import MAX_MODELING_ATTEMPTS, build_graph
from vault_agent.models.contract import ContractOwner
from vault_agent.profiling import load_profiling
from vault_agent.report import build_report
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import (
    RESOLUTION_SAME_AS,
    ColumnProfile,
    DVModel,
    EntityResolution,
    FlagKind,
    ProposedMapping,
    SourceTable,
    VaultAgentState,
    split_concept_key,
)
from vault_agent.trace import JsonlTraceWriter

app = typer.Typer(help="Agentic AI for Data Vault 2.0 automation.", no_args_is_help=True)

# The CLI's own module logger: crash recovery and checkpoint pruning report through it (both
# are best-effort hygiene whose failures must never reach the user's console as noise —
# `--debug` surfaces them, WP5 §5.4).
logger = logging.getLogger(__name__)

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

    # WP23 §2.1: the LOGICAL model as a first-class output — the round-trip source a later
    # `run --existing <this dir>` reads. automatedv.yml is RENDERED macro metadata and
    # cannot yield it back losslessly (it has no descriptions, requirement_ids, sat_type,
    # driving keys, source_table or Hub.sources), so brownfield mode gets its own file
    # rather than a lossy reconstruction. Deterministic: sorted keys, no timestamps.
    if _has_constructs(state.dv_model):
        meta_dir = out_dir / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / DV_MODEL_FILENAME).write_text(
            yaml.safe_dump(state.dv_model.model_dump(mode="json"), sort_keys=True),
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

    if state.resolutions.proposals:
        (out_dir / "resolutions.review.yml").write_text(
            _render_resolutions_review(state.resolutions), encoding="utf-8"
        )

    review_queue = assemble_review_queue(state)
    if review_queue.items:
        (out_dir / "review-queue.md").write_text(
            render_review_queue_md(review_queue), encoding="utf-8"
        )

    # WP23 §2.7: the extension diff — what this run changed about the vault it extends.
    # Extension runs only; a greenfield tree must not gain the file (pinned).
    if state.artifacts.extension_diff:
        (out_dir / DIFF_FILENAME).write_text(
            render_extension_diff_md(
                ExtensionDiff(**state.artifacts.extension_diff),
                state.existing_source or "the existing vault",
            ),
            encoding="utf-8",
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
        # WP23 §2.1: the logical model dump — the round-trip source for `run --existing`.
        "model": 1 if _has_constructs(state.dv_model) else 0,
        "contracts": len(state.artifacts.contracts),
        "mappings": len(mapping.proposals),
        "resolutions": len(state.resolutions.proposals),
        "review_items": len(review_queue.items),
        "report": 1,
        "extension_diff": 1 if state.artifacts.extension_diff else 0,
    }


def _render_resolutions_review(resolutions: EntityResolution) -> str:
    """Render the human-editable entity-resolution review file (WP29 §2.5).

    Set a concept's ``resolution`` to an existing construct's name (or ``NEW`` /
    ``same_as_candidate`` / ``unresolved``) and resume with
    ``vault-agent resume --resolutions <file>``, or decide one with
    ``vault-agent resume --resolve "concept=hub_name"``.

    The file leads with ``category`` and ``evidence`` rather than ``confidence``, deliberately:
    the category is derived from the evidence (WP29 §2.3) while the confidence is the model's
    own claim, and the spike measured the latter to be the less trustworthy of the two."""
    doc: dict[str, Any] = {
        "resolutions": [
            {
                "concept": p.concept,
                "resolution": p.resolution,
                **({"same_as": p.same_as} if p.same_as else {}),
                "category": p.category,
                "evidence": list(p.evidence),
                "confidence": round(p.confidence, 3),
                "ratification_status": p.ratification_status,
            }
            for p in resolutions.proposals
        ]
    }
    header = (
        "# Entity resolution against the existing vault — review & ratify (WP29).\n"
        "# resolution: <existing construct name> | NEW | same_as_candidate | unresolved\n"
        "# Then:  vault-agent resume --resolutions <this file>\n"
        "# Or:    vault-agent resume --resolve \"concept=hub_name\"\n"
        "# A merge is applied ONLY after you ratify it — an unratified proposal never\n"
        "# steers the modeler, because a wrong merge writes foreign keys into live history.\n"
    )
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _render_mappings_review(mapping: ProposedMapping) -> str:
    """Render the human-editable business↔source mapping review file (WP9 §5).

    Edit a proposal's ``table``/``column`` (or move an ``unresolved`` concept up into
    ``proposals`` with a source) and resume with ``vault-agent resume --mappings <file>``, or
    override one concept with ``vault-agent resume --map "concept=TABLE.COLUMN"``."""
    doc: dict[str, Any] = {
        "proposals": [
            {
                # WP32: `key` is the concept's identity — two hubs can share a business-key
                # label and differ only in entity, so the label alone cannot address one of
                # them. `--map` and an edited file accept the key; a bare label still works
                # wherever it is unambiguous.
                "key": p.key,
                "concept": p.concept,
                "entity": p.entity,
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


# ``pending.json`` is SINGLE-SLOT per output directory: one unfinished run per ``--out``.
# Concurrent runs into one directory are unsupported (they would overwrite each other's
# pointer); the run-start pruning below relies on this to recognise orphaned threads.
PENDING_PAUSED = "paused"
PENDING_CRASHED = "crashed"

# Exit codes. 0 = finalized or paused, 1 = the pipeline failed, 2 = Click/typer usage error;
# 3 (WP25 §2.2) = the run completed but its model does not validate, so a wrapper script can
# tell a failed model from a good one instead of reading the console.
EXIT_NOT_VALIDATED = 3


def _write_pending(
    out_dir: Path,
    thread_id: str,
    input_doc: Path,
    *,
    phase: str = PENDING_PAUSED,
    error: str | None = None,
) -> None:
    """Point at the unfinished run's thread, and say WHY it is unfinished (WP17 §2.1).

    ``phase`` is ``paused`` (the HITL interrupt — today's semantics) or ``crashed`` (a node
    raised); a crashed file also carries a one-line ``error`` summary. The shape stays
    ``dict[str, str]``, and a file written before WP17 (no ``phase`` key) reads as paused."""
    path = _pending_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"thread_id": thread_id, "input": str(input_doc), "phase": phase}
    if error is not None:
        payload["error"] = error
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_pending(out_dir: Path) -> dict[str, str] | None:
    """The unfinished-run pointer, or None when there is none.

    Raises an attributable ``ValueError`` naming the file and the problem when the pointer
    exists but is unusable (WP27 §2.3, house loader style — see
    ``source_schema.load_source_schemas``). ``pending.json`` is a documented file users are
    pointed at and may hand-edit, so a truncated or reshaped one must not surface as a raw
    ``JSONDecodeError`` traceback. Callers that treat a broken pointer as "no pointer"
    (crash reporting, orphan pruning) already catch it."""
    path = _pending_path(out_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict) or not data.get("thread_id"):
        raise ValueError(
            f"{path}: expected a JSON object with a 'thread_id' key naming the run's "
            f"checkpoint thread"
        )
    return cast(dict[str, str], data)


def _pending_phase(pending: dict[str, str]) -> str:
    """The pending run's phase; a pre-WP17 file without the key is a paused run."""
    return pending.get("phase") or PENDING_PAUSED


def _clear_pending(out_dir: Path) -> None:
    _pending_path(out_dir).unlink(missing_ok=True)


def _state_from_result(result: dict[str, Any]) -> VaultAgentState:
    """Rebuild the state from an ainvoke result, dropping LangGraph's __interrupt__ key."""
    data = {key: value for key, value in result.items() if key != "__interrupt__"}
    return VaultAgentState.model_validate(data)


async def _state_from_checkpoint(compiled: Any, config: RunnableConfig) -> VaultAgentState:
    """The state as of the thread's latest checkpoint — every node that completed.

    Shared by the interactive resume (a paused run's state) and the crash path (the
    artifacts-so-far a failed run already paid for): both need "what is on disk for this
    thread", and there must be exactly one way to ask that."""
    snapshot = await compiled.aget_state(config)
    return VaultAgentState.model_validate(snapshot.values)


async def _prune_orphan_threads(saver: Any, out_dir: Path, keep: str) -> None:
    """Delete checkpoint threads no longer reachable from the CLI (WP17 §2.4).

    WP5 §5.5 prunes a *finalised* run's thread, but a run killed hard (SIGKILL, a closed
    laptop) never reaches any except-branch, so its thread would linger forever — the
    unbounded growth WP5 fixed, reintroduced through the crash path. ``pending.json`` is
    single-slot, so exactly two threads are reachable: the pending one and the run starting
    now. Everything else is unreachable by construction.

    Pruning is hygiene: any failure here is logged and swallowed — it must never be the
    reason a run cannot start."""
    referenced = {keep}
    try:
        pending = _read_pending(out_dir)
    except (OSError, ValueError):  # unreadable/corrupt pointer: keep everything, prune nothing
        logger.debug("pending.json unreadable; skipping orphan pruning", exc_info=True)
        return
    if pending and pending.get("thread_id"):
        referenced.add(pending["thread_id"])
    try:
        await saver.setup()
        # Verified against langgraph-checkpoint-sqlite 3.1.1 (re-checked 2026-08-08 on the
        # bump from 3.1.0, which ships no release notes): `conn` is the documented aiosqlite
        # connection and checkpoints are keyed by thread_id in `checkpoints`. This is raw SQL
        # against an internal table — the one touchpoint here that a schema change would break
        # silently, so it is exercised directly on every bump rather than assumed from semver.
        async with saver.conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
            rows = await cursor.fetchall()
        orphans = sorted({str(row[0]) for row in rows} - referenced)
    except Exception:  # noqa: BLE001 - hygiene must never block a run
        logger.debug("could not list checkpoint threads; skipping orphan pruning", exc_info=True)
        return
    for thread_id in orphans:
        try:
            await saver.adelete_thread(thread_id)
        except Exception:  # noqa: BLE001 - same reason
            logger.debug("could not prune orphan thread %s", thread_id, exc_info=True)
    if orphans:
        logger.info("pruned %d orphaned checkpoint thread(s)", len(orphans))


async def _invoke_checkpointed(
    out_dir: Path,
    thread_id: str,
    payload: Any,
    *,
    input_doc: Path,
    trace: bool,
    write: bool,
    prune_orphans: bool = False,
) -> tuple[VaultAgentState, bool]:
    """One checkpointed graph invocation: trace on, saver open, crash recovery around it.

    ``payload`` is what a run needs to continue: an initial ``VaultAgentState`` for a fresh
    run, ``Command(resume=decision)`` past the HITL interrupt, or ``None`` to continue a
    crashed thread (LangGraph resumes from the latest checkpoint and re-executes the failed
    node — verified against langgraph 1.2.4, not assumed).

    Returns ``(state, paused)``. A finalised run's thread is pruned (WP5 §5.5); a paused or
    crashed one keeps its thread, since that is exactly what ``resume`` continues."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    with _tracing(out_dir, thread_id, trace):
        async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
            saver.serde = _checkpoint_serde()
            if prune_orphans:
                await _prune_orphan_threads(saver, out_dir, keep=thread_id)
            compiled = build_graph().compile(checkpointer=saver)
            try:
                result = await compiled.ainvoke(payload, config=config)
            except Exception as exc:
                await _rescue(out_dir, thread_id, input_doc, compiled, config, exc, write)
                raise
            paused = "__interrupt__" in result
            if not paused:
                await saver.adelete_thread(thread_id)
    return _state_from_result(result), paused


async def _rescue(
    out_dir: Path,
    thread_id: str,
    input_doc: Path,
    compiled: Any,
    config: RunnableConfig,
    exc: BaseException,
    write: bool,
) -> None:
    """Record the crash and write the artifacts-so-far — never masking ``exc`` (WP17 §2.2).

    Everything the completed nodes produced sits in the thread's latest checkpoint; without
    this the user pays for the LLM work and gets nothing, since ``write_outputs`` never runs
    and ``resume`` refuses without a pointer. The ``crashed`` pending file is what makes the
    thread reachable again — the thread_id is printed nowhere else.

    Every step is individually guarded: a rescue failure is logged and swallowed, so the
    caller re-raises the ORIGINAL exception, which is the one the user needs to see."""
    try:
        _write_pending(
            out_dir, thread_id, input_doc,
            phase=PENDING_CRASHED, error=f"{type(exc).__name__}: {exc}",
        )
    except OSError:
        logger.warning("could not record the crashed run's pending pointer", exc_info=True)
    if not write:
        return  # --no-write: the user asked for no artifacts; the pointer is enough
    try:
        state = await _state_from_checkpoint(compiled, config)
        counts = write_outputs(state, out_dir)
        logger.info("crash recovery wrote %d raw-vault model(s) so far", counts["models"])
    except Exception:  # noqa: BLE001 - a rescue must never replace the failure it rescues
        logger.warning("could not write the crashed run's artifacts-so-far", exc_info=True)


async def _run_pipeline(
    input_doc: Path,
    out_dir: Path,
    source_schemas: list[SourceTable] | None = None,
    profiling: dict[str, dict[str, ColumnProfile]] | None = None,
    trace: bool = True,
    write: bool = True,
    existing_model: DVModel | None = None,
    existing_source: str | None = None,
) -> tuple[VaultAgentState, bool, str]:
    """Run the pipeline under a persistent checkpointer. Returns (state, paused, thread_id);
    ``paused`` is true when the human-in-the-loop checkpoint interrupted the run.

    ``source_schemas`` (from ``--source-schema``) activates ADR-0004 grounding; ``profiling``
    (from ``--profiling``, WP9) feeds the business↔source mapper. Empty/``None`` leaves both
    inert. ``trace`` (WP15) writes the run's LLM transcript beside its checkpoint. ``write``
    is the ``--no-write`` flag, honoured by the crash rescue as well. ``existing_model``
    (from ``--existing``, WP23) switches the run to brownfield mode; ``None`` = greenfield,
    and resume needs no flag because the model is persisted in the checkpoint."""
    thread_id = uuid4().hex
    _checkpoint_dir(out_dir).mkdir(parents=True, exist_ok=True)
    state, paused = await _invoke_checkpointed(
        out_dir,
        thread_id,
        # LangGraph's generic ainvoke doesn't infer our pydantic state as StateT;
        # passing VaultAgentState is correct at runtime.
        VaultAgentState(
            input_documents=[str(input_doc)],
            source_schemas=source_schemas or [],
            profiling=profiling or {},
            existing_model=existing_model,
            existing_source=existing_source,
        ),
        input_doc=input_doc,
        trace=trace,
        write=write,
        prune_orphans=True,
    )
    return state, paused, thread_id


async def _resume_pipeline(
    out_dir: Path,
    thread_id: str,
    decision: dict[str, Any],
    trace: bool = True,
    input_doc: Path | None = None,
    write: bool = True,
) -> tuple[VaultAgentState, bool]:
    """Resume a paused run on the same thread with the human's decision.

    The trace appends to the same thread's jsonl, so a paused+resumed run is one transcript."""
    return await _invoke_checkpointed(
        out_dir,
        thread_id,
        Command(resume=decision),
        input_doc=input_doc or Path("unknown"),
        trace=trace,
        write=write,
    )


async def _continue_pipeline(
    out_dir: Path,
    thread_id: str,
    trace: bool = True,
    input_doc: Path | None = None,
    write: bool = True,
) -> tuple[VaultAgentState, bool]:
    """Continue a CRASHED run on its own thread (WP17 §2.3).

    ``ainvoke(None, ...)`` picks the thread up at its latest checkpoint and re-executes the
    node that failed — verified against the installed langgraph 1.2.4 rather than assumed.
    Completed nodes are not re-run, so only the failed step is paid for twice."""
    return await _invoke_checkpointed(
        out_dir,
        thread_id,
        None,
        input_doc=input_doc or Path("unknown"),
        trace=trace,
        write=write,
    )


async def _discard_pending(out_dir: Path, thread_id: str) -> None:
    """Drop an unfinished run: its checkpoint thread and the pending pointer (WP17 §2.3)."""
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
        saver.serde = _checkpoint_serde()
        await saver.adelete_thread(thread_id)
    _clear_pending(out_dir)


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


def _parse_resolve(spec: str) -> tuple[str, str]:
    """Parse ``concept=<construct name | NEW | same_as_candidate | unresolved>`` (WP29)."""
    concept, sep, answer = spec.partition("=")
    concept, answer = concept.strip(), answer.strip()
    if not sep or not concept or not answer:
        raise ValueError(
            f"invalid --resolve {spec!r}; expected 'concept=hub_name' (or =NEW / "
            f"=same_as_candidate / =unresolved)"
        )
    return concept, answer


def _resolutions_from_file(path: Path) -> dict[str, str]:
    """Read an edited ``resolutions.review.yml`` into ``{concept: answer}`` (WP29 §2.5).

    Every entry carrying a ``resolution`` becomes a ratification. The appliers refuse an
    answer that names a construct the existing vault does not have, so a typo here cannot
    invent a hub any more than the resolver itself can."""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected a mapping with a 'resolutions' list")
    answers: dict[str, str] = {}
    for entry in document.get("resolutions", []) or []:
        if isinstance(entry, dict) and entry.get("concept") and entry.get("resolution"):
            answers[str(entry["concept"])] = str(entry["resolution"])
    return answers


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
        # WP32: prefer the entry's `key` (the concept's identity); fall back to the bare
        # label for a hand-written or pre-WP32 file, where the appliers resolve it if it is
        # unambiguous.
        ref = entry.get("key") or entry.get("concept")
        table, column = entry.get("table"), entry.get("column")
        if ref and table and column:
            overrides[str(ref)] = f"{table}.{column}"
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
        if not isinstance(entry, dict) or not (entry.get("key") or entry.get("concept")):
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
            out[str(entry.get("key") or entry["concept"])] = feeds
    return out


def _build_decision(
    owners: list[str],
    accept: bool,
    mappings: dict[str, str] | None = None,
    mapping_sources: dict[str, list[dict[str, str]]] | None = None,
    resolutions: dict[str, str] | None = None,
    links: dict[str, bool] | None = None,
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
        "resolutions": resolutions or {},
        # WP34: {"<Table>.<Column>": build it / decline it}. Same payload, same appliers, so
        # a flag and an interactive answer cannot mean different things.
        "links": links or {},
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
    owner: list[str] | None,
    accept: bool,
    mappings: Path | None,
    map_: list[str] | None,
    resolutions: Path | None = None,
    resolve: list[str] | None = None,
) -> bool:
    """True when ``resume`` was given any explicit decision — flags win, no prompt is shown."""
    return (
        bool(owner)
        or accept
        or mappings is not None
        or bool(map_)
        or resolutions is not None
        or bool(resolve)
    )


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
) -> VaultAgentState:
    """Answer a checkpoint in the terminal, then resume the same thread in-process.

    **Returns the state as of the last resume**, which the caller must use: the resumes here
    revise ``modeling_attempts`` and ``validation_report``, and ``_state_from_result`` builds a
    NEW state object rather than mutating the caller's. Returning ``None`` was harmless while
    sign-off was the only pause — a paused state there already carried the validator's final
    verdict — but WP29 pauses BEFORE the modeler, so the caller's copy says
    ``modeling_attempts == 0`` and ``passed == False`` no matter how the run ended, and
    :func:`_exit_unvalidated` would exempt it and report success for a model that never
    validated (review of PR #16).

    Two checkpoints reach this. At the WP29 resolution checkpoint (before modelling) it
    collects resolutions; at the sign-off checkpoint it collects owners/mappings and shows any
    (interactively-unfixable) validation errors. Either way it gates on a confirm that mirrors
    ``--accept`` exactly, assembles the decision via the existing ``_build_decision`` and
    resumes via ``_resume_pipeline``. On decline / skip-all / Ctrl-C it leaves the checkpoint
    intact — ``pending.json`` and the checkpointer thread survive and the flag-based ``resume``
    still works — and prints the resume instructions.

    The loop is load-bearing since WP29's second checkpoint: answering the resolution pause
    carries the run on to the sign-off pause, and both are answered in the one session."""
    while True:
        at_resolution = _paused_at_resolution(state)
        owners: list[str]
        overrides: dict[str, str]
        resolutions: dict[str, str]
        try:
            if at_resolution:
                owners, overrides = [], {}
                resolutions = _collect_resolution_decision(console, state)
                confirm = "Ratify the remaining proposal(s) as shown and build the model?"
            else:
                owners, overrides = _collect_decision(console, state)
                resolutions = {}
                confirm = "Accept and finalize?"
                for issue in state.validation_report.issues:
                    if issue.severity == "error":
                        console.print(
                            f"[red]validation error[/red] {issue.code}: {issue.message}"
                        )
            if not _prompter.confirm(console, confirm, default=False):
                _report_paused(console, out, state=state)
                return state
        except KeyboardInterrupt:
            console.print("\n[yellow]Aborted — checkpoint kept.[/yellow]")
            _report_paused(console, out, state=state)
            return state

        decision = _build_decision(owners, True, overrides, {}, resolutions)
        state, paused = asyncio.run(_resume_pipeline(out, thread_id, decision, trace))
        _print_summary(console, state)
        counts = write_outputs(state, out)
        _report_written(console, counts, out)
        if not paused:
            _clear_pending(out)
            console.print("\n[bold green]Checkpoint cleared — run finalized.[/bold green]")
            return state
        # Paused again — the resolution checkpoint handing over to sign-off, in the normal
        # case. Loop with the new state and answer that one too.


def _collect_resolution_decision(
    console: Console, state: VaultAgentState
) -> dict[str, str]:
    """Walk the pending entity resolutions, collecting per-concept answers (WP29).

    Capability-parity with the flags, like :func:`_collect_decision`: it collects the same
    strings ``resume --resolve "<concept>=<answer>"`` takes and hands them to the same
    ``_build_decision`` → ``apply_resolution_decision`` path — no decision semantics here. An
    empty answer leaves the proposal as proposed, which the following confirm then ratifies;
    the way to REJECT a proposed merge is to answer ``NEW``, and the prompt says so."""
    answers: dict[str, str] = {}
    for proposal in pending_resolution_decisions(state.resolutions):
        label, entity = split_concept_key(proposal.concept)
        origin = f" (from {entity})" if entity else ""
        claim = (
            f"equivalent to {proposal.same_as!r} but keyed differently"
            if proposal.resolution == RESOLUTION_SAME_AS
            else f"IS the existing {proposal.resolution!r}"
        )
        console.print(
            f"  [yellow]{label}[/yellow]{origin}: proposed {claim} "
            f"[dim]({proposal.category}, confidence {proposal.confidence:.2f})[/dim]"
        )
        for line in proposal.evidence:
            console.print(f"    [dim]{line}[/dim]")
        answer = _prompter.text(
            console,
            f"Decision for {label!r} (a construct name, or NEW to reject the merge, "
            "Enter to keep as proposed)",
        ).strip()
        if answer:
            answers[proposal.concept] = answer
    return answers


async def _paused_state(out: Path, thread_id: str) -> VaultAgentState:
    """Load an interrupted run's state from its checkpoint (for a flag-less interactive resume)."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out)) as saver:
        saver.serde = _checkpoint_serde()
        compiled = build_graph().compile(checkpointer=saver)
        return await _state_from_checkpoint(compiled, config)


def _has_constructs(model: DVModel) -> bool:
    return bool(model.hubs or model.links or model.satellites)


def _construct_count(model: DVModel) -> int:
    return len(model.hubs) + len(model.links) + len(model.satellites)


def _print_summary(console: Console, state: VaultAgentState) -> None:
    model = state.dv_model
    report = state.validation_report
    verdict = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"
    n_schemas = len(state.source_schemas)
    grounding = f"on ({n_schemas} source table(s))" if n_schemas else "off"
    prior = state.existing_model
    mode = (
        f"extension ({_construct_count(prior)} existing construct(s))"
        if prior is not None
        else "greenfield"
    )
    console.print(
        f"  mode:          {mode}\n"
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


def _report_paused(
    console: Console, out: Path, write: bool = True, state: VaultAgentState | None = None
) -> None:
    """Print how to answer the checkpoint — in terms of what actually blocks it.

    WP25 made the validation-error blocker reachable, and for it there is no owner to
    assign: telling the human to pass ``--owner`` would send them looking for an asset that
    does not exist. When no contract is waiting for an owner, the instructions name the two
    decisions that DO apply. Without a state (or with owners pending) the message is
    byte-identical to the pre-WP25 one.

    Since WP29 a run can also pause BEFORE modelling, where none of the above applies: that
    pause is reported by :func:`_report_paused_at_resolution` instead."""
    if state is not None and _paused_at_resolution(state):
        _report_paused_at_resolution(console, out, state)
        if not write:
            console.print(_NO_WRITE_RESUME_NOTE)
        return
    no_owner_to_assign = state is not None and not any(
        item.kind == "contract_owner" for item in assemble_review_queue(state).items
    )
    if no_owner_to_assign:
        console.print(
            "\n[bold yellow]Paused at the human-in-the-loop checkpoint.[/bold yellow] "
            "Nothing here can be fixed by assigning an owner — decide on the model:\n"
            f"  [cyan]vault-agent resume --out {out} --accept[/cyan]   "
            "(keep it, errors and all — for diagnosis)\n"
            f"  [cyan]vault-agent resume --out {out} --discard[/cyan]  "
            "(throw the run away and start over)"
        )
    else:
        console.print(
            "\n[bold yellow]Paused at the human-in-the-loop checkpoint.[/bold yellow] "
            "Assign the contract owner(s) above and resume:\n"
            f"  [cyan]vault-agent resume --out {out} "
            '--owner "<asset>=<Name> <<email>>"[/cyan]\n'
            "  (repeat --owner per asset; add --accept to proceed once owners are set)"
        )
    if not write:
        # The pause was reached under --no-write, but resume defaults to writing: say so,
        # rather than letting the next command surprise the user with artifacts (WP21 §2.7).
        console.print(_NO_WRITE_RESUME_NOTE)


# WP21 §2.7, shared by both pause reports so the two cannot drift apart.
_NO_WRITE_RESUME_NOTE = (
    "  [dim]note: this run used --no-write; the resume above WILL write artifacts "
    "unless you pass --no-write again[/dim]"
)


def _paused_at_resolution(state: VaultAgentState) -> bool:
    """True when this pause is the WP29 resolution checkpoint, not the sign-off one.

    Both clauses are typed state, and together they are exact. ``modeling_attempts == 0`` says
    the modeler has not run, which is true only between the resolver and the modeler; the
    pending-decision clause says something is actually waiting there. At the sign-off
    checkpoint the first clause is false, and a resolution pause cannot reach sign-off
    undecided because the node re-executes and would simply pause again."""
    return state.modeling_attempts == 0 and bool(
        pending_resolution_decisions(state.resolutions)
    )


def _report_paused_at_resolution(
    console: Console, out: Path, state: VaultAgentState
) -> None:
    """Print the pending merges/same-as candidates and the three ways to answer them.

    Naming the concepts here matters more than at sign-off: this decision changes what gets
    BUILT, and the alternative to reading them is opening a YAML file to find out what the run
    is waiting for."""
    pending = pending_resolution_decisions(state.resolutions)
    console.print(
        f"\n[bold yellow]Paused before modelling — {len(pending)} entity resolution(s) "
        f"need a decision.[/bold yellow] Each one says a concept the new source introduces "
        f"IS something the existing vault already holds:"
    )
    for proposal in pending:
        label, entity = split_concept_key(proposal.concept)
        origin = f" (from {entity})" if entity else ""
        target = (
            f"equivalent to [cyan]{proposal.same_as}[/cyan] but keyed differently"
            if proposal.resolution == RESOLUTION_SAME_AS
            else f"IS the existing [cyan]{proposal.resolution}[/cyan]"
        )
        console.print(
            f"  [yellow]{label}[/yellow]{origin}: {target} "
            f"[dim]({proposal.category}, confidence {proposal.confidence:.2f})[/dim]"
        )
    console.print(
        "\n  [cyan]vault-agent resume --out "
        f"{out} --resolve \"<concept>=<construct>\"[/cyan]  (decide one; repeat per concept)\n"
        f"  [cyan]vault-agent resume --out {out} --resolutions "
        f"{out}/resolutions.review.yml[/cyan]  (edit the file, then ratify it)\n"
        f"  [cyan]vault-agent resume --out {out} --accept[/cyan]   "
        "(ratify all of the above as proposed)"
    )


def _exit_unvalidated(console: Console, state: VaultAgentState, out: Path) -> None:
    """Exit 3 when the run ends carrying a model that did not validate (WP25 §2.2).

    Called at every point where a CLI invocation ENDS — finalized or paused. The
    discriminator is ``validation_report.passed``, not paused-ness: a pause for an
    unassigned contract owner is a normal outcome and keeps exit 0, while a run whose model
    never validated must not report success even after a human accepted it, because the
    artifacts on disk still carry the known errors. Exit 1 stays "the pipeline failed", 2
    stays Click's usage error, so 3 is unambiguous for a wrapper script.

    A run paused at the WP29 resolution checkpoint is exempt: it stopped BEFORE the modeler
    ever ran, so ``validation_report.passed`` is still its ``False`` default and there is no
    model that could have failed. Discriminated on ``modeling_attempts``, which is 0 on
    exactly that path and non-zero everywhere else this function is reached."""
    if state.validation_report.passed or state.modeling_attempts == 0:
        return
    errors = sum(1 for issue in state.validation_report.issues if issue.severity == "error")
    console.print(
        f"\n[bold red]The model did not validate[/bold red] after "
        f"{MAX_MODELING_ATTEMPTS} modeling attempt(s): {errors} validation error(s) remain. "
        f"They are listed in the review queue and in [cyan]{out}/report.html[/cyan]. These "
        f"artifacts are for diagnosis and remediation — not for deployment."
    )
    raise typer.Exit(code=EXIT_NOT_VALIDATED)


def _report_crashed(console: Console, out: Path) -> None:
    """What a crashed run leaves behind, and the two ways forward (WP17 §2.2).

    Silent unless a crashed pointer actually exists: a failure before the checkpointer opened
    (a bad input path, say) leaves nothing to resume, and promising recovery there would be a
    lie the user would waste a command discovering."""
    try:
        pending = _read_pending(out)
    except (OSError, ValueError):
        return
    if pending is None or _pending_phase(pending) != PENDING_CRASHED:
        return
    console.print(
        f"\n[yellow]The work completed before the failure is checkpointed[/yellow] and any "
        f"artifacts produced so far were written to [cyan]{out}/[/cyan]. Continue where it "
        f"stopped, or throw it away:\n"
        f"  [cyan]vault-agent resume --out {out}[/cyan]\n"
        f"  [cyan]vault-agent resume --out {out} --discard[/cyan]"
    )


@app.command()
def run(
    input_doc: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, dir_okay=False,
                       help="Requirements document (.md, .txt, .pdf, or .docx)."),
    ],
    out: Annotated[
        Path,
        typer.Option(
            "--out", "-o",
            help="Output directory for generated artifacts (one unfinished run per directory).",
        ),
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
    existing: Annotated[
        Path | None,
        typer.Option(
            "--existing", "-e", exists=True,
            help="Extend a previously generated vault: its output directory (or its "
                 "metadata/dv_model.yml). Without this, the run is greenfield.",
        ),
    ] = None,
    write: Annotated[
        bool,
        typer.Option(
            "--write/--no-write",
            help="Write ARTIFACTS to disk (run state — checkpoint, pending, trace — is "
                 "always written, or the run could not be resumed).",
        ),
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
        # WP23: brownfield mode. A malformed/pre-WP23 --existing is an attributable message
        # here, before any LLM token is spent — same reasoning as the other input loaders.
        prior_model = load_existing_model(existing) if existing else None
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]Could not load an input file:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    try:
        state, paused, thread_id = asyncio.run(
            _run_pipeline(
                input_doc, out, schemas, profiles, trace, write, prior_model,
                str(existing) if existing else None,
            )
        )
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
        # The run's checkpointed work is NOT lost: _run_pipeline's rescue already recorded a
        # crashed pending pointer and wrote the artifacts-so-far (WP17 §2.2).
        console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
        _report_crashed(console, out)
        if _DEBUG:
            raise  # --debug: full traceback on top of the recovery instructions
        raise typer.Exit(code=1) from exc

    _print_summary(console, state)

    if write:
        counts = write_outputs(state, out)
        _report_written(console, counts, out)
    else:
        console.print("\n[dim]--no-write: nothing written to disk.[/dim]")

    if paused:
        # Run state (checkpoint, pending pointer, trace) is not an artifact and is written
        # even under --no-write (WP21 §2.7): a paused run that could not be resumed would be
        # strictly worse than useless.
        _write_pending(out, thread_id, input_doc)
        # WP12: answer the checkpoint in-terminal when interactive (needs write, since the
        # in-process resume finalises to disk); otherwise print today's resume instructions.
        if write and _is_interactive(interactive):
            state = _interactive_checkpoint(console, out, thread_id, state, trace)
        else:
            _report_paused(console, out, write, state)
    else:
        _clear_pending(out)

    # Last statement on every path. The validator is the only writer of the report and no node
    # after it revises the verdict — but the STATE OBJECT is replaced by every resume, so this
    # must read the one the interactive checkpoint returned, not the one it was given. Before
    # WP29 the distinction did not bite: the only pause was sign-off, past the validator, so a
    # stale copy already carried the final verdict. A resolution pause is before the modeler.
    _exit_unvalidated(console, state, out)


def _resume_paused(
    console: Console,
    out: Path,
    pending: dict[str, str],
    *,
    owner: list[str] | None,
    accept: bool,
    mappings: Path | None,
    map_: list[str] | None,
    trace: bool,
    interactive: bool | None,
    write: bool = True,
    resolutions: Path | None = None,
    resolve: list[str] | None = None,
    link: list[str] | None = None,
    no_link: list[str] | None = None,
) -> None:
    """Answer the HITL checkpoint of a paused run — the flag path and the WP12 prompt.

    Shared by ``resume`` on a paused pending file and by ``resume`` on a CRASHED one that
    reached the checkpoint after being continued: the capability-parity rule (WP12) says the
    two must offer exactly the same ways to decide, which they only do if it is one code
    path."""
    thread_id = pending["thread_id"]
    input_doc = Path(pending.get("input", "unknown"))

    # WP12: with no decision flags and a TTY, drive the checkpoint interactively — load the
    # paused state from its checkpoint, then prompt + resume in-process. Flags win (no prompt),
    # and a non-TTY keeps today's flag-based path byte-identical.
    if (
        not _has_decision_flags(owner, accept, mappings, map_, resolutions, resolve)
        and write
        and _is_interactive(interactive)
    ):
        try:
            state = asyncio.run(_paused_state(out, thread_id))
        except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly
            if _DEBUG:
                raise
            console.print(f"[bold red]Resume failed:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"[bold]Resuming[/bold] paused run in [cyan]{out}/[/cyan] (interactive) …\n")
        _print_checkpoint(console, assemble_review_queue(state))
        state = _interactive_checkpoint(console, out, thread_id, state, trace)
        _exit_unvalidated(console, state, out)
        return

    try:
        overrides = _mappings_from_file(mappings) if mappings else {}
        for spec in map_ or []:
            concept, target = _parse_map(spec)
            overrides[concept] = target
        multi = _mapping_sources_from_file(mappings) if mappings else {}
        ratified = _resolutions_from_file(resolutions) if resolutions else {}
        for spec in resolve or []:
            concept, answer = _parse_resolve(spec)
            ratified[concept] = answer
        # WP34: an explicit --no-link wins over --link for the same proposal, because a
        # deliberate refusal must never be overridden by a bulk answer given earlier.
        link_answers: dict[str, bool] = {spec: True for spec in link or []}
        link_answers.update({spec: False for spec in no_link or []})
        decision = _build_decision(
            owner or [], accept, overrides, multi, ratified, link_answers
        )
    except (ValueError, OSError) as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]Resuming[/bold] paused run in [cyan]{out}/[/cyan] …\n")
    try:
        state, paused = asyncio.run(
            _resume_pipeline(out, thread_id, decision, trace, input_doc, write)
        )
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
        console.print(f"[bold red]Resume failed:[/bold red] {exc}")
        _report_crashed(console, out)
        if _DEBUG:
            raise  # --debug: full traceback on top of the recovery instructions
        raise typer.Exit(code=1) from exc

    _print_summary(console, state)
    if write:
        counts = write_outputs(state, out)
        _report_written(console, counts, out)
    else:
        console.print("\n[dim]--no-write: nothing written to disk.[/dim]")

    if paused:
        _report_paused(console, out, write, state)
    else:
        # Finalised: the run state goes regardless of --no-write — it governs artifacts, and
        # a finished run has nothing left to resume (the thread is already pruned).
        _clear_pending(out)
        console.print("\n[bold green]Checkpoint cleared — run finalized.[/bold green]")

    # Accepting at the checkpoint does not make an invalid model valid (WP25 §2.2).
    _exit_unvalidated(console, state, out)


@app.command()
def resume(
    out: Annotated[
        Path,
        typer.Option(
            "--out", "-o",
            help="Output directory of the paused or crashed run (one unfinished run each).",
        ),
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
    resolutions: Annotated[
        Path | None,
        typer.Option("--resolutions", help="Edited resolutions.review.yml to ratify (WP29)."),
    ] = None,
    resolve: Annotated[
        list[str] | None,
        typer.Option(
            "--resolve",
            help="Ratify one entity resolution: 'concept=hub_name' (or =NEW) (WP29).",
        ),
    ] = None,
    link: Annotated[
        list[str] | None,
        typer.Option(
            "--link",
            help="Build a proposed link: 'Table.Column' (WP34).",
        ),
    ] = None,
    no_link: Annotated[
        list[str] | None,
        typer.Option(
            "--no-link",
            help="Decline a proposed link: 'Table.Column' (WP34).",
        ),
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
    write: Annotated[
        bool,
        typer.Option(
            "--write/--no-write",
            help="Write ARTIFACTS to disk (run state — checkpoint, pending, trace — is "
                 "always written); repeat --no-write to keep a --no-write run dry.",
        ),
    ] = True,
    discard: Annotated[
        bool,
        typer.Option(
            "--discard",
            help="Throw the unfinished run away: delete its checkpoint thread and pending file.",
        ),
    ] = False,
) -> None:
    """Continue an unfinished run: paused at the checkpoint, or crashed mid-pipeline."""
    console = Console()
    try:
        pending = _read_pending(out)
    except (OSError, ValueError) as exc:
        # The pointer exists but is unusable — say which file and why, and offer the two ways
        # out. A raw traceback here would be the product's fault, not the user's (WP27 §2.3).
        # NOT offering --discard here on purpose: it reads the same pointer and would fail
        # with the same message. Deleting the file by hand is the only way through.
        console.print(
            f"[bold red]Cannot read the unfinished-run pointer:[/bold red] {exc}\n"
            f"  Repair that file, or delete it to abandon the run (its checkpoint thread "
            f"is then pruned by the next [cyan]vault-agent run[/cyan] into [cyan]{out}/[/cyan])."
        )
        raise typer.Exit(code=1) from exc
    if pending is None:
        console.print(f"[bold red]No unfinished run found[/bold red] under [cyan]{out}/[/cyan].")
        raise typer.Exit(code=1)
    thread_id = pending["thread_id"]
    phase = _pending_phase(pending)

    if discard:
        # The escape hatch for a run not worth continuing (a deterministic failure, an input
        # that was wrong in the first place): drop the thread AND the pointer, and say so.
        asyncio.run(_discard_pending(out, thread_id))
        console.print(
            f"[bold]Discarded[/bold] the {phase} run (thread {thread_id}) in "
            f"[cyan]{out}/[/cyan]: checkpoint thread and pending.json deleted. Artifacts "
            f"already written are untouched."
        )
        return

    if phase == PENDING_CRASHED:
        error = pending.get("error", "unknown error")
        console.print(
            f"[bold]Continuing[/bold] crashed run in [cyan]{out}/[/cyan] "
            f"(it failed with: {error}) …\n"
        )
        try:
            state, paused = asyncio.run(
                _continue_pipeline(
                    out, thread_id, trace, Path(pending.get("input", "unknown")), write
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly
            # The rescue already refreshed the crashed pending file with THIS error, so the
            # thread stays continuable; a deterministic failure simply repeats until the human
            # fixes the cause or discards the run.
            console.print(f"[bold red]The run failed again:[/bold red] {exc}")
            _report_crashed(console, out)
            if _DEBUG:
                raise
            raise typer.Exit(code=1) from exc

        _print_summary(console, state)
        if write:
            counts = write_outputs(state, out)
            _report_written(console, counts, out)
        else:
            console.print("\n[dim]--no-write: nothing written to disk.[/dim]")
        if not paused:
            _clear_pending(out)
            console.print("\n[bold green]Checkpoint cleared — run finalized.[/bold green]")
            _exit_unvalidated(console, state, out)
            return
        # The continued run reached the HITL checkpoint: it is a paused run from here on.
        # Record that first (so a hard kill right here still leaves a resumable pointer),
        # then handle the checkpoint exactly as `run` does — decision flags apply
        # immediately, a TTY prompts, a pipe prints the instructions. What must NOT happen
        # is deciding for the human: they have not seen this checkpoint yet.
        input_path = Path(pending.get("input", "unknown"))
        _write_pending(out, thread_id, input_path)
        pending = {"thread_id": thread_id, "input": str(input_path)}
        if not _has_decision_flags(
            owner, accept, mappings, map_, resolutions, resolve
        ):
            if write and _is_interactive(interactive):
                state = _interactive_checkpoint(console, out, thread_id, state, trace)
            else:
                _report_paused(console, out, write, state)
            _exit_unvalidated(console, state, out)
            return

    _resume_paused(
        console, out, pending,
        owner=owner, accept=accept, mappings=mappings, map_=map_,
        resolutions=resolutions, resolve=resolve, link=link, no_link=no_link,
        trace=trace, interactive=interactive, write=write,
    )


if __name__ == "__main__":
    app()
