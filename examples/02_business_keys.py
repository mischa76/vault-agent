"""End-to-end smoke run of the first two pipeline steps.

Chains Requirements Parser -> Business Key Identifier on the bank-account toy document
and prints the proposed business keys. Requires ANTHROPIC_API_KEY (read from .env).

Run from the repo root:

    uv run python examples/02_business_keys.py
"""
import asyncio

from rich.console import Console
from rich.table import Table

from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"


async def main() -> None:
    console = Console()
    state = VaultAgentState(input_documents=[INPUT_DOC])

    console.print(f"[bold]1/2 Parsing[/bold] {INPUT_DOC} …")
    state = await RequirementsParserAgent().run(state)
    console.print(f"  → {len(state.requirements)} requirements")

    console.print("[bold]2/2 Identifying business keys[/bold] …")
    state = await BusinessKeyIdentifierAgent().run(state)
    console.print(f"  → {len(state.business_keys)} candidates")

    if state.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in state.errors:
            console.print(f"  - {err}")

    table = Table(title=f"{len(state.business_keys)} business key candidates")
    table.add_column("Entity", style="cyan", no_wrap=True)
    table.add_column("Field", style="green")
    table.add_column("Score", justify="right", style="magenta")
    table.add_column("Rationale")
    for cand in sorted(state.business_keys, key=lambda c: c.score, reverse=True):
        table.add_row(cand.entity, cand.field, f"{cand.score:.2f}", cand.rationale)
    console.print(table)


if __name__ == "__main__":
    asyncio.run(main())
