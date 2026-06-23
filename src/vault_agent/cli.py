"""Command-line entry point for the Vault-Agent pipeline.

``vault-agent run <requirements.md>`` runs the full LangGraph pipeline on a requirements
document and writes the generated AutomateDV/dbt models, the AutomateDV metadata, and the
finalized ADR to an output directory.

The artifact-writing logic lives in ``write_outputs`` (a pure function) so it can be tested
without the graph or an API key; the ``run`` command wires the graph to it.
"""
import asyncio
import json
import re
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

from vault_agent import state as _state_module
from vault_agent.agents.orchestrator import (
    HumanReviewQueue,
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.graph import build_graph
from vault_agent.state import VaultAgentState

app = typer.Typer(help="Agentic AI for Data Vault 2.0 automation.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Agentic AI for Data Vault 2.0 automation."""
    # Present so `run` stays an explicit subcommand instead of collapsing into the app.


def _adr_filename(adr_text: str) -> str:
    """Derive a stable filename from an ADR's first heading."""
    first_line = adr_text.lstrip().splitlines()[0] if adr_text.strip() else ""
    match = re.match(r"#\s*(ADR-\d+):\s*(.*)", first_line)
    if not match:
        return "ADR.md"
    number, title = match.group(1), match.group(2)
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", title).strip("-").lower()
    return f"{number}-{slug}.md" if slug else f"{number}.md"


def write_outputs(state: VaultAgentState, out_dir: Path) -> dict[str, int]:
    """Write dbt models, AutomateDV metadata, and ADRs to ``out_dir``; return counts."""
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, sql in state.artifacts.dbt_models.items():
        (models_dir / f"{name}.sql").write_text(sql, encoding="utf-8")

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
            (adr_dir / _adr_filename(adr)).write_text(adr, encoding="utf-8")

    if state.artifacts.contracts or state.artifacts.dbt_tests:
        contracts_dir = out_dir / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        for contract in state.artifacts.contracts:
            asset = str(contract.get("name", "contract"))
            (contracts_dir / f"{asset}.contract.yml").write_text(
                yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
            )
        for asset, tests_yaml in state.artifacts.dbt_tests.items():
            (contracts_dir / f"{asset}.tests.yml").write_text(tests_yaml, encoding="utf-8")

    review_queue = assemble_review_queue(state)
    if review_queue.items:
        (out_dir / "review-queue.md").write_text(
            render_review_queue_md(review_queue), encoding="utf-8"
        )

    return {
        "models": len(state.artifacts.dbt_models),
        "adrs": len(state.adrs),
        "metadata": 1 if state.artifacts.automatedv_yaml else 0,
        "contracts": len(state.artifacts.contracts),
        "review_items": len(review_queue.items),
    }


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


async def _run_pipeline(input_doc: Path, out_dir: Path) -> tuple[VaultAgentState, bool, str]:
    """Run the pipeline under a persistent checkpointer. Returns (state, paused, thread_id);
    ``paused`` is true when the human-in-the-loop checkpoint interrupted the run."""
    thread_id = uuid4().hex
    _checkpoint_dir(out_dir).mkdir(parents=True, exist_ok=True)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
        saver.serde = _checkpoint_serde()
        compiled = build_graph().compile(checkpointer=saver)
        result = await compiled.ainvoke(
            # LangGraph's generic ainvoke doesn't infer our pydantic state as StateT;
            # passing VaultAgentState is correct at runtime.
            VaultAgentState(input_documents=[str(input_doc)]),  # type: ignore[arg-type]
            config=config,
        )
    return _state_from_result(result), "__interrupt__" in result, thread_id


async def _resume_pipeline(
    out_dir: Path, thread_id: str, decision: dict[str, Any]
) -> tuple[VaultAgentState, bool]:
    """Resume a paused run on the same thread with the human's decision."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_db(out_dir)) as saver:
        saver.serde = _checkpoint_serde()
        compiled = build_graph().compile(checkpointer=saver)
        result = await compiled.ainvoke(Command(resume=decision), config=config)
    return _state_from_result(result), "__interrupt__" in result


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


def _build_decision(owners: list[str], accept: bool) -> dict[str, Any]:
    parsed: dict[str, dict[str, str | None]] = {}
    for spec in owners:
        asset, owner = _parse_owner(spec)
        parsed[asset] = owner
    return {"owners": parsed, "accept": accept}


def _print_summary(console: Console, state: VaultAgentState) -> None:
    model = state.dv_model
    report = state.validation_report
    verdict = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"
    console.print(
        f"  requirements:  {len(state.requirements)}\n"
        f"  business keys: {len(state.business_keys)}\n"
        f"  model:         {len(model.hubs)} hubs, {len(model.links)} links, "
        f"{len(model.satellites)} satellites\n"
        f"  dbt models:    {len(state.artifacts.dbt_models)}\n"
        f"  contracts:     {len(state.artifacts.contracts)}\n"
        f"  validation:    {verdict} ({len(report.issues)} issue(s))"
    )
    _print_checkpoint(console, assemble_review_queue(state))


_CHECKPOINT_HEADINGS: dict[str, str] = {
    "validation_error": "Validation errors (block agreement)",
    "contract_owner": "Contract owners to assign (block agreement)",
    "validation_warning": "Validation warnings (advisory)",
    "review_flag": "Review flags (advisory)",
}
_CHECKPOINT_ORDER = (
    "validation_error",
    "contract_owner",
    "validation_warning",
    "review_flag",
)


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
    for kind in _CHECKPOINT_ORDER:
        group = grouped.get(kind)
        if not group:
            continue
        console.print(f"  [bold]{_CHECKPOINT_HEADINGS[kind]}[/bold]")
        for item in group:
            detail = f" — {item.detail}" if item.detail else ""
            console.print(f"    - {item.summary}{detail}")


def _report_written(console: Console, counts: dict[str, int], out: Path) -> None:
    console.print(
        f"\n[bold]Wrote[/bold] {counts['models']} model(s), {counts['contracts']} "
        f"contract(s), {counts['adrs']} ADR(s), {counts['metadata']} metadata file(s), "
        f"{counts['review_items']} review item(s) to [cyan]{out}/[/cyan]"
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
    write: Annotated[
        bool, typer.Option("--write/--no-write", help="Write artifacts to disk."),
    ] = True,
) -> None:
    """Run the full pipeline on a requirements document and write the artifacts."""
    console = Console()
    console.print(f"[bold]Running Vault-Agent pipeline[/bold] on {input_doc} …\n")
    try:
        state, paused, thread_id = asyncio.run(_run_pipeline(input_doc, out))
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
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
) -> None:
    """Resume a run paused at the human-in-the-loop checkpoint with owner assignments."""
    console = Console()
    pending = _read_pending(out)
    if pending is None:
        console.print(f"[bold red]No paused run found[/bold red] under [cyan]{out}/[/cyan].")
        raise typer.Exit(code=1)

    try:
        decision = _build_decision(owner or [], accept)
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]Resuming[/bold] paused run in [cyan]{out}/[/cyan] …\n")
    try:
        state, paused = asyncio.run(_resume_pipeline(out, pending["thread_id"], decision))
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
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
