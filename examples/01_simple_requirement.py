"""End-to-end smoke run of the Requirements Parser agent.

Feeds the bank-account toy document through the real Anthropic-backed agent and prints
the extracted requirements. Requires ANTHROPIC_API_KEY (read from .env via config.settings).

Run from the repo root:

    uv run python examples/01_simple_requirement.py
"""
import asyncio

from rich.console import Console
from rich.table import Table

from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"


async def main() -> None:
    console = Console()
    state = VaultAgentState(input_documents=[INPUT_DOC])

    console.print(f"[bold]Parsing[/bold] {INPUT_DOC} …")
    agent = RequirementsParserAgent()
    state = await agent.run(state)

    if state.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in state.errors:
            console.print(f"  - {err}")

    table = Table(title=f"{len(state.requirements)} requirements extracted")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Actor")
    table.add_column("Action")
    table.add_column("Object")
    table.add_column("Text")
    for req in state.requirements:
        table.add_row(
            req.id,
            req.category,
            req.actor or "—",
            req.action or "—",
            req.obj or "—",
            req.text,
        )
    console.print(table)


if __name__ == "__main__":
    asyncio.run(main())
