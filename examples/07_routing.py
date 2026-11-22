"""Deterministic demo of the validator -> modeler self-correction loop.

The conditional edge in the graph sends a failing model back to the modeler until it passes
or the retry cap is hit. To show this without burning API calls, this example injects stub
agents and a scripted validator (fails twice, then passes) into build_graph, then prints the
order in which nodes ran. Runs without ANTHROPIC_API_KEY.

Run from the repo root:

    uv run python examples/07_routing.py
"""
import asyncio

from rich.console import Console

from vault_agent.agents.base import BaseAgent
from vault_agent.graph import MAX_MODELING_ATTEMPTS, PIPELINE, build_graph
from vault_agent.state import ValidationReport, VaultAgentState


class RecordingAgent(BaseAgent):
    prompt_path = "unused.md"  # type: ignore[assignment]

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        state.decisions.append({"agent": self.name})
        return state


class ScriptedValidator(BaseAgent):
    prompt_path = "unused.md"  # type: ignore[assignment]

    def __init__(self, verdicts: list[bool]) -> None:
        self.verdicts = verdicts
        self.calls = 0

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        passed = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        state.validation_report = ValidationReport(passed=passed)
        state.decisions.append({"agent": "validator", "passed": passed})
        return state


async def run_scenario(console: Console, title: str, verdicts: list[bool]) -> None:
    agents: dict[str, BaseAgent] = {name: RecordingAgent(name) for name in PIPELINE}
    agents["validator"] = ScriptedValidator(verdicts)
    app = build_graph(agents).compile()

    out = await app.ainvoke(VaultAgentState())
    state = VaultAgentState.model_validate(out)

    console.print(f"\n[bold]{title}[/bold]")
    decisions = state.decisions
    for i, d in enumerate(decisions):
        mark = ""
        if d["agent"] == "validator":
            looped_back = i + 1 < len(decisions) and decisions[i + 1]["agent"] == "dv2_modeler"
            if d["passed"]:
                mark = " [green]✓ passed[/green]"
            elif looped_back:
                mark = " [red]✗ failed → loop back[/red]"
            else:
                mark = " [red]✗ failed → cap reached, stop[/red]"
        console.print(f"  {i + 1:>2}. {d['agent']}{mark}")
    modeler_runs = sum(1 for d in state.decisions if d["agent"] == "dv2_modeler")
    verdict = "PASSED" if state.validation_report.passed else f"GAVE UP after {modeler_runs}"
    console.print(f"  → modeler ran {modeler_runs}×, result: [bold]{verdict}[/bold]")


async def main() -> None:
    console = Console()
    console.print(f"Retry cap: MAX_MODELING_ATTEMPTS = {MAX_MODELING_ATTEMPTS}")
    await run_scenario(
        console, "Scenario A — fails twice, then self-corrects", [False, False, True]
    )
    await run_scenario(console, "Scenario B — never converges (hits the cap)", [False])


if __name__ == "__main__":
    asyncio.run(main())
