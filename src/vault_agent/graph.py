"""LangGraph state machine wiring all agents together.

The graph is intentionally thin – business logic stays in the agent nodes.
"""
from langgraph.graph import StateGraph

from vault_agent.state import VaultAgentState

def build_graph() -> StateGraph[VaultAgentState]:
    """Build but do not compile the agent graph."""
    g: StateGraph[VaultAgentState] = StateGraph(VaultAgentState)
    # Nodes will be added as agents are implemented:
    # g.add_node("orchestrator", orchestrator_node)
    # g.add_node("requirements_parser", requirements_parser_node)
    # ...

    # Edges (placeholder):
    # g.set_entry_point("orchestrator")
    # g.add_edge("orchestrator", END)

    return g
