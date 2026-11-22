"""End-to-end smoke run of the first three pipeline steps.

Chains Requirements Parser -> Business Key Identifier -> DV2.0 Modeler on the bank-account
toy document and prints the derived Data Vault model. Requires ANTHROPIC_API_KEY (.env).

Run from the repo root:

    uv run python examples/03_dv_model.py
"""
import asyncio

from rich.console import Console
from rich.tree import Tree

from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"


async def main() -> None:
    console = Console()
    state = VaultAgentState(input_documents=[INPUT_DOC])

    console.print(f"[bold]1/3 Parsing[/bold] {INPUT_DOC} …")
    state = await RequirementsParserAgent().run(state)
    console.print(f"  → {len(state.requirements)} requirements")

    console.print("[bold]2/3 Identifying business keys[/bold] …")
    state = await BusinessKeyIdentifierAgent().run(state)
    console.print(f"  → {len(state.business_keys)} candidates")

    console.print("[bold]3/3 Modelling the Data Vault[/bold] …")
    state = await Dv2ModelerAgent().run(state)
    model = state.dv_model
    console.print(
        f"  → {len(model.hubs)} hubs, {len(model.links)} links, "
        f"{len(model.satellites)} satellites"
    )

    if state.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in state.errors:
            console.print(f"  - {err}")

    tree = Tree("[bold]Data Vault model[/bold]")
    hubs_node = tree.add("[cyan]Hubs[/cyan]")
    for hub in model.hubs:
        hubs_node.add(f"{hub.name}  [dim](bk: {hub.business_key})[/dim]")
    links_node = tree.add("[green]Links[/green]")
    for link in model.links:
        links_node.add(f"{link.name}  [dim]({' ↔ '.join(link.connected_hubs)})[/dim]")
    sats_node = tree.add("[magenta]Satellites[/magenta]")
    for sat in model.satellites:
        sats_node.add(f"{sat.name} → {sat.parent}  [dim]({', '.join(sat.attributes)})[/dim]")
    console.print(tree)

    if state.adrs:
        console.print("\n[bold]Draft ADR fragment:[/bold]")
        console.print(state.adrs[-1])


if __name__ == "__main__":
    asyncio.run(main())
