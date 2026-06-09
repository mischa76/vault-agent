"""Tests for the LangGraph wiring.

Uses recording stub agents so the graph runs end-to-end in CI without an API key. These
assert orchestration only (node set, order, state flow) — agent behaviour is covered by the
per-agent unit tests.
"""
from vault_agent.agents.base import BaseAgent
from vault_agent.graph import PIPELINE, build_graph, default_agents
from vault_agent.state import VaultAgentState


class _RecordingAgent(BaseAgent):
    prompt_path = "unused.md"  # type: ignore[assignment]

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        state.decisions.append({"agent": self.name})
        return state


def _stub_agents() -> dict[str, BaseAgent]:
    return {name: _RecordingAgent(name) for name in PIPELINE}


def test_default_agents_cover_the_pipeline() -> None:
    agents = default_agents()
    assert set(agents) == set(PIPELINE)


def test_graph_exposes_all_pipeline_nodes() -> None:
    compiled = build_graph(_stub_agents()).compile()
    assert set(PIPELINE).issubset(set(compiled.nodes))


async def test_pipeline_runs_all_agents_in_order() -> None:
    compiled = build_graph(_stub_agents()).compile()

    out = await compiled.ainvoke(VaultAgentState(input_documents=["doc.md"]))
    result = VaultAgentState.model_validate(out)

    assert [d["agent"] for d in result.decisions] == PIPELINE
    # Input state flows through untouched.
    assert result.input_documents == ["doc.md"]
