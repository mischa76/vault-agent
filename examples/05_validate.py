"""End-to-end smoke run of the first five pipeline steps.

Chains Requirements Parser -> Business Key Identifier -> DV2.0 Modeler -> Code Generator
-> Validator on the bank-account toy document and prints the validation report. Steps 1-3
require ANTHROPIC_API_KEY (.env); the generator and validator are deterministic.

Run from the repo root:

    uv run python examples/05_validate.py
"""
import asyncio

from rich.console import Console
from rich.table import Table

from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import VaultAgentState

INPUT_DOC = "examples/inputs/bank_account_requirements.md"

_SEVERITY_STYLE = {"error": "bold red", "warning": "yellow"}


async def main() -> None:
    console = Console()
    state = VaultAgentState(input_documents=[INPUT_DOC])

    state = await RequirementsParserAgent().run(state)
    console.print(f"1/5 Parsed → {len(state.requirements)} requirements")
    state = await BusinessKeyIdentifierAgent().run(state)
    console.print(f"2/5 Business keys → {len(state.business_keys)} candidates")
    state = await Dv2ModelerAgent().run(state)
    m = state.dv_model
    console.print(
        f"3/5 Modelled → {len(m.hubs)} hubs, {len(m.links)} links, {len(m.satellites)} sats"
    )
    state = await CodeGeneratorAgent().run(state)
    console.print(f"4/5 Generated → {len(state.artifacts.dbt_models)} dbt models")
    state = await ValidatorAgent().run(state)

    report = state.validation_report
    verdict = "[bold green]PASSED[/bold green]" if report.passed else "[bold red]FAILED[/bold red]"
    console.print(f"5/5 Validation → {verdict}\n")

    if report.issues:
        table = Table(title="Validation issues")
        table.add_column("Severity")
        table.add_column("Code", style="cyan")
        table.add_column("Construct", style="green")
        table.add_column("Message")
        for issue in report.issues:
            style = _SEVERITY_STYLE.get(issue["severity"], "")
            table.add_row(
                f"[{style}]{issue['severity']}[/{style}]" if style else issue["severity"],
                issue["code"], issue["construct"], issue["message"],
            )
        console.print(table)
    else:
        console.print("No issues found.")


if __name__ == "__main__":
    asyncio.run(main())
