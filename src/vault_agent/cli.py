"""Command-line entry point for the Vault-Agent pipeline.

``vault-agent run <requirements.md>`` runs the full LangGraph pipeline on a requirements
document and writes the generated AutomateDV/dbt models, the AutomateDV metadata, and the
finalized ADR to an output directory.

The artifact-writing logic lives in ``write_outputs`` (a pure function) so it can be tested
without the graph or an API key; the ``run`` command wires the graph to it.
"""
import asyncio
import re
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

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

    return {
        "models": len(state.artifacts.dbt_models),
        "adrs": len(state.adrs),
        "metadata": 1 if state.artifacts.automatedv_yaml else 0,
    }


async def _run_pipeline(input_doc: Path) -> VaultAgentState:
    compiled = build_graph().compile()
    result = await compiled.ainvoke(VaultAgentState(input_documents=[str(input_doc)]))
    return VaultAgentState.model_validate(result)


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
        f"  validation:    {verdict} ({len(report.issues)} issue(s))"
    )
    if state.errors:
        console.print("\n[bold yellow]Flags for human review:[/bold yellow]")
        for err in state.errors:
            console.print(f"  - {err}")


@app.command()
def run(
    input_doc: Annotated[
        Path,
        typer.Argument(exists=True, readable=True, dir_okay=False,
                       help="Requirements document (markdown/text)."),
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
        state = asyncio.run(_run_pipeline(input_doc))
    except Exception as exc:  # noqa: BLE001 - surface any runtime failure cleanly to the CLI
        console.print(f"[bold red]Pipeline failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(console, state)

    if write:
        counts = write_outputs(state, out)
        console.print(
            f"\n[bold]Wrote[/bold] {counts['models']} model(s), {counts['adrs']} ADR(s), "
            f"{counts['metadata']} metadata file(s) to [cyan]{out}/[/cyan]"
        )
    else:
        console.print("\n[dim]--no-write: nothing written to disk.[/dim]")


if __name__ == "__main__":
    app()
