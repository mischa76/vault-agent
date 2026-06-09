"""End-to-end smoke run of the first four pipeline steps.

Chains Requirements Parser -> Business Key Identifier -> DV2.0 Modeler -> Code Generator
on the bank-account toy document and prints the generated AutomateDV/dbt models. Steps 1-3
require ANTHROPIC_API_KEY (.env); the code generator itself is deterministic.

Run from the repo root:

    uv run python examples/04_generate_code.py
"""
import asyncio

from rich.console import Console
from rich.syntax import Syntax

from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"


async def main() -> None:
    console = Console()
    state = VaultAgentState(input_documents=[INPUT_DOC])

    console.print(f"[bold]1/4 Parsing[/bold] {INPUT_DOC} …")
    state = await RequirementsParserAgent().run(state)
    console.print(f"  → {len(state.requirements)} requirements")

    console.print("[bold]2/4 Identifying business keys[/bold] …")
    state = await BusinessKeyIdentifierAgent().run(state)
    console.print(f"  → {len(state.business_keys)} candidates")

    console.print("[bold]3/4 Modelling the Data Vault[/bold] …")
    state = await Dv2ModelerAgent().run(state)
    m = state.dv_model
    console.print(f"  → {len(m.hubs)} hubs, {len(m.links)} links, {len(m.satellites)} sats")

    console.print("[bold]4/4 Generating AutomateDV/dbt models[/bold] …")
    state = await CodeGeneratorAgent().run(state)
    console.print(f"  → {len(state.artifacts.dbt_models)} dbt models")

    if state.errors:
        console.print("\n[bold yellow]Flags / errors:[/bold yellow]")
        for err in state.errors:
            console.print(f"  - {err}")

    # Show one generated model of each kind, if present.
    models = state.artifacts.dbt_models
    samples = [
        next((n for n in models if n.startswith("hub_")), None),
        next((n for n in models if n.startswith("link_")), None),
        next((n for n in models if n.startswith("sat_")), None),
    ]
    for name in filter(None, samples):
        console.print(f"\n[bold cyan]models/{name}.sql[/bold cyan]")
        console.print(Syntax(models[name], "sql", theme="ansi_dark"))


if __name__ == "__main__":
    asyncio.run(main())
