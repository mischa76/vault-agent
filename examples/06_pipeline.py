"""End-to-end run of the full pipeline via the compiled LangGraph.

Unlike examples 01-05 (which call agents directly), this drives the compiled graph from
vault_agent.graph — the same wiring the orchestrator will use. Steps 1-3 require
ANTHROPIC_API_KEY (.env); the code generator and validator are deterministic.

Run from the repo root:

    uv run python examples/06_pipeline.py
"""
import asyncio

from rich.console import Console

from vault_agent.graph import build_graph
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"


async def main() -> None:
    console = Console()
    app = build_graph().compile()

    console.print("[bold]Running the Vault-Agent pipeline via LangGraph[/bold] …")
    out = await app.ainvoke(VaultAgentState(input_documents=[INPUT_DOC]))
    state = VaultAgentState.model_validate(out)

    m = state.dv_model
    report = state.validation_report
    verdict = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"

    console.print(
        f"\n  requirements: {len(state.requirements)}\n"
        f"  business keys: {len(state.business_keys)}\n"
        f"  model: {len(m.hubs)} hubs, {len(m.links)} links, {len(m.satellites)} sats\n"
        f"  dbt models: {len(state.artifacts.dbt_models)}\n"
        f"  validation: {verdict} ({len(report.issues)} issue(s))"
    )

    console.print("\n[bold]Step audit trail:[/bold]")
    for decision in state.decisions:
        console.print(f"  - {decision}")

    if state.errors:
        console.print("\n[bold yellow]Flags:[/bold yellow]")
        for err in state.errors:
            console.print(f"  - {err}")

    if state.adrs:
        console.print("\n[bold]Finalized ADR (excerpt):[/bold]")
        excerpt = "\n".join(state.adrs[0].splitlines()[:14])
        console.print(excerpt)


if __name__ == "__main__":
    asyncio.run(main())
