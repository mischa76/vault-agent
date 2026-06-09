"""LangGraph state machine wiring all agents together.

The graph is intentionally thin — business logic stays in the agent nodes (see CLAUDE.md).
This module only wires the implemented agents into a linear pipeline and turns each one
into a node. Conditional routing (e.g. loop back to the modeler when validation fails) and
the orchestrator/ADR-author/data-contract agents come later.

Agents are injectable so the graph can be tested with stubbed LLMs; the defaults construct
the real agents. Construction needs no API key — the Anthropic client is built lazily on
first ``run`` — so ``build_graph`` and ``compile`` are safe without credentials.
"""
from collections.abc import Awaitable, Callable

from langgraph.graph import END, StateGraph

from vault_agent.agents.base import BaseAgent
from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import VaultAgentState

# The pipeline order. Each name is both the node id and the key in the agents mapping.
PIPELINE: list[str] = [
    "requirements_parser",
    "business_key_identifier",
    "dv2_modeler",
    "code_generator",
    "validator",
]

Node = Callable[[VaultAgentState], Awaitable[VaultAgentState]]


def default_agents() -> dict[str, BaseAgent]:
    """Construct the real agents (no API key needed until they run)."""
    return {
        "requirements_parser": RequirementsParserAgent(),
        "business_key_identifier": BusinessKeyIdentifierAgent(),
        "dv2_modeler": Dv2ModelerAgent(),
        "code_generator": CodeGeneratorAgent(),
        "validator": ValidatorAgent(),
    }


def _make_node(agent: BaseAgent) -> Node:
    async def node(state: VaultAgentState) -> VaultAgentState:
        return await agent.run(state)

    return node


def build_graph(agents: dict[str, BaseAgent] | None = None) -> StateGraph[VaultAgentState]:
    """Build (but do not compile) the linear agent pipeline."""
    agents = agents or default_agents()
    graph: StateGraph[VaultAgentState] = StateGraph(VaultAgentState)

    for name in PIPELINE:
        # LangGraph's overloaded add_node stubs don't accept a plain async state->state
        # callable; the wiring is exercised by tests/test_graph.py.
        graph.add_node(name, _make_node(agents[name]))  # type: ignore[call-overload]

    graph.set_entry_point(PIPELINE[0])
    for src, dst in zip(PIPELINE, PIPELINE[1:], strict=False):
        graph.add_edge(src, dst)
    graph.add_edge(PIPELINE[-1], END)

    return graph
