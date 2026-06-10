"""LangGraph state machine wiring all agents together.

The graph is intentionally thin — business logic stays in the agent nodes (see CLAUDE.md).
This module wires the implemented agents into a pipeline, turns each into a node, and adds
one conditional edge: when validation fails, route back to the modeler to re-model (with the
validation issues fed back as guidance), bounded by a retry cap to avoid infinite loops.

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

# How many times the modeler may run before the pipeline gives up on a failing model.
MAX_MODELING_ATTEMPTS = 3


def route_after_validation(state: VaultAgentState) -> str:
    """Loop back to the modeler while validation fails and the retry budget remains."""
    if state.validation_report.passed:
        return END
    attempts = sum(1 for d in state.decisions if d.get("agent") == "dv2_modeler")
    if attempts >= MAX_MODELING_ATTEMPTS:
        return END
    return "dv2_modeler"


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

    # The validator either ends the run or sends the model back for another attempt.
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {"dv2_modeler": "dv2_modeler", END: END},
    )

    return graph
