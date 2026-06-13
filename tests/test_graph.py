"""Tests for the LangGraph wiring.

Uses recording stub agents so the graph runs end-to-end in CI without an API key. These
assert orchestration only (node set, order, state flow) — agent behaviour is covered by the
per-agent unit tests.
"""
from vault_agent.agents.base import BaseAgent
from vault_agent.graph import (
    MAX_MODELING_ATTEMPTS,
    NODES,
    build_graph,
    default_agents,
)
from vault_agent.state import ValidationReport, VaultAgentState


class _RecordingAgent(BaseAgent):
    prompt_path = "unused.md"  # type: ignore[assignment]

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        # Mirror the real modeler's counter increment so the retry guard, which now reads
        # state.modeling_attempts rather than counting decisions, is exercised faithfully.
        if self.name == "dv2_modeler":
            state.modeling_attempts += 1
        state.decisions.append({"agent": self.name})
        return state


class _StubValidator(BaseAgent):
    """Reports a scripted pass/fail sequence (last value repeats)."""

    prompt_path = "unused.md"  # type: ignore[assignment]

    def __init__(self, verdicts: list[bool]) -> None:
        self.verdicts = verdicts
        self.calls = 0

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        passed = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        issues = [] if passed else [{"severity": "error", "code": "X", "message": "m"}]
        state.validation_report = ValidationReport(passed=passed, issues=issues)
        state.decisions.append({"agent": "validator", "passed": passed})
        return state


def _stub_agents() -> dict[str, BaseAgent]:
    agents: dict[str, BaseAgent] = {name: _RecordingAgent(name) for name in NODES}
    agents["validator"] = _StubValidator([True])  # pass so the happy path ends in one go
    return agents


def _routing_agents(validator: BaseAgent) -> dict[str, BaseAgent]:
    agents = _stub_agents()
    agents["validator"] = validator
    return agents


def _modeler_runs(state: VaultAgentState) -> int:
    # The retry cap is enforced via the explicit counter, not by counting decisions.
    return state.modeling_attempts


def test_default_agents_cover_all_nodes() -> None:
    agents = default_agents()
    assert set(agents) == set(NODES)


def test_graph_exposes_all_nodes() -> None:
    compiled = build_graph(_stub_agents()).compile()
    assert set(NODES).issubset(set(compiled.nodes))


async def test_pipeline_runs_all_agents_in_order() -> None:
    compiled = build_graph(_stub_agents()).compile()

    out = await compiled.ainvoke(VaultAgentState(input_documents=["doc.md"]))
    result = VaultAgentState.model_validate(out)

    # On success the ADR author runs after the validator.
    assert [d["agent"] for d in result.decisions] == NODES
    # Input state flows through untouched.
    assert result.input_documents == ["doc.md"]


async def test_failing_validation_loops_back_to_modeler_then_passes() -> None:
    # Fail the first attempt, pass the second.
    compiled = build_graph(_routing_agents(_StubValidator([False, True]))).compile()

    out = await compiled.ainvoke(VaultAgentState())
    result = VaultAgentState.model_validate(out)

    assert result.validation_report.passed is True
    assert _modeler_runs(result) == 2  # initial attempt + one retry


async def test_persistent_failure_stops_at_retry_cap() -> None:
    compiled = build_graph(_routing_agents(_StubValidator([False]))).compile()

    out = await compiled.ainvoke(VaultAgentState())
    result = VaultAgentState.model_validate(out)

    assert result.validation_report.passed is False
    assert _modeler_runs(result) == MAX_MODELING_ATTEMPTS  # bounded, no infinite loop
    # L-4: the run ends without the ADR author, and the modeler accumulates no drafts.
    assert result.adrs == []
