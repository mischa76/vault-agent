"""LangGraph state machine wiring all agents together.

The graph is intentionally thin — business logic stays in the agent nodes (see CLAUDE.md).
This module wires the implemented agents into a pipeline, turns each into a node, and adds
one conditional edge: when validation fails, route back to the modeler to re-model (with the
validation issues fed back as guidance), bounded by a retry cap to avoid infinite loops.
When validation passes, the ADR author documents the accepted model before the run ends.

Agents are injectable so the graph can be tested with stubbed LLMs; the defaults construct
the real agents. Construction needs no API key — the Anthropic client is built lazily on
first ``run`` — so ``build_graph`` and ``compile`` are safe without credentials.
"""
from collections.abc import Awaitable, Callable

from langgraph.graph import END, StateGraph

from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.agents.base import BaseAgent
from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.data_contract import DataContractAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.entity_resolver import EntityResolverAgent
from vault_agent.agents.orchestrator import HumanCheckpointAgent, OrchestratorAgent
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.agents.source_mapper import SourceMapperAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import VaultAgentState

# The orchestrator plans the run and validates inputs, then hands off to the pipeline.
ENTRY_NODE = "orchestrator"

# The linear pipeline order. Each name is both the node id and the agents-mapping key.
PIPELINE: list[str] = [
    "requirements_parser",
    "business_key_identifier",
    # Data contracts describe the source-to-staging assets, so they depend only on the
    # requirements, business keys, and (optional) source schema — not the DV model. Placed
    # before modeling, the contract is unaffected by the validation re-model loop, which
    # routes back to dv2_modeler, never re-running this node.
    "data_contract",
    # WP29: entity resolution runs BEFORE the modeler and only on a grounded extension run
    # (inert otherwise). Once the modeler names a construct, WP23's merge_models folds it by
    # name and the decision is already made — so "is this new PARTNER the existing
    # hub_customer?" has to be proposed, and ratifiable, before modelling.
    "entity_resolver",
    "dv2_modeler",
    "code_generator",
    "validator",
]

# Reached only after the validator passes. The business↔source mapper (WP9) runs first on the
# now-stable/validated model — outside the re-model loop — then the human-in-the-loop
# checkpoint (ADR-0006) where a human signs off / assigns owners / ratifies mappings, then the
# ADR author documents the model. (The mapper sits here rather than before code generation, as
# WP9 §4's diagram suggests, because the validator validates the code generator's artifacts —
# so code generation cannot move after the validator; the mapper re-binds staging itself.)
SOURCE_MAPPER_NODE = "source_mapper"
HUMAN_CHECKPOINT_NODE = "human_checkpoint"
POST_VALIDATION_NODE = "adr_author"
NODES: list[str] = [
    ENTRY_NODE, *PIPELINE, SOURCE_MAPPER_NODE, HUMAN_CHECKPOINT_NODE, POST_VALIDATION_NODE
]
# What the orchestrator records as the planned downstream stages (everything after itself).
PLANNED_STAGES: list[str] = [
    *PIPELINE, SOURCE_MAPPER_NODE, HUMAN_CHECKPOINT_NODE, POST_VALIDATION_NODE
]

Node = Callable[[VaultAgentState], Awaitable[VaultAgentState]]

# How many times the modeler may run before the pipeline gives up on a failing model.
MAX_MODELING_ATTEMPTS = 3


def route_after_validation(state: VaultAgentState) -> str:
    """On success route to the source mapper (then the human checkpoint and the ADR author);
    loop back to the modeler while the retry budget remains; at the cap hand the failing
    model to the human checkpoint.

    The exhausted budget routes to HUMAN_CHECKPOINT_NODE, not END (WP25 §2.1): a model that
    will not validate is precisely the case ADR-0006's gate exists for, and
    ``HumanReviewQueue.requires_signoff`` already treats a validation error as blocking — a
    branch that could never fire while this returned END, which also made ``review-queue.md``
    point at a checkpoint that did not exist.

    It deliberately does NOT route through the source mapper first, unlike the passing path:
    mapping concepts of a model the human may well discard spends LLM calls on output that
    may never be used. The human decides first; a run accepted over its errors simply has no
    mappings section."""
    if state.validation_report.passed:
        return SOURCE_MAPPER_NODE
    if state.modeling_attempts >= MAX_MODELING_ATTEMPTS:
        return HUMAN_CHECKPOINT_NODE
    return "dv2_modeler"


def default_agents() -> dict[str, BaseAgent]:
    """Construct the real agents (no API key needed until they run)."""
    return {
        "orchestrator": OrchestratorAgent(planned_stages=PLANNED_STAGES),
        "requirements_parser": RequirementsParserAgent(),
        "business_key_identifier": BusinessKeyIdentifierAgent(),
        "data_contract": DataContractAgent(),
        "entity_resolver": EntityResolverAgent(),
        "dv2_modeler": Dv2ModelerAgent(),
        "code_generator": CodeGeneratorAgent(),
        "validator": ValidatorAgent(),
        "source_mapper": SourceMapperAgent(),
        "human_checkpoint": HumanCheckpointAgent(),
        "adr_author": AdrAuthorAgent(),
    }


def _make_node(agent: BaseAgent) -> Node:
    async def node(state: VaultAgentState) -> VaultAgentState:
        return await agent.run(state)

    return node


def build_graph(agents: dict[str, BaseAgent] | None = None) -> StateGraph[VaultAgentState]:
    """Build (but do not compile) the linear agent pipeline."""
    agents = agents or default_agents()
    graph: StateGraph[VaultAgentState] = StateGraph(VaultAgentState)

    for name in NODES:
        # LangGraph's overloaded add_node stubs don't accept a plain async state->state
        # callable; the wiring is exercised by tests/test_graph.py.
        graph.add_node(name, _make_node(agents[name]))  # type: ignore[call-overload]

    graph.set_entry_point(ENTRY_NODE)
    graph.add_edge(ENTRY_NODE, PIPELINE[0])
    for src, dst in zip(PIPELINE, PIPELINE[1:], strict=False):
        graph.add_edge(src, dst)

    # Validator passes -> mapper -> human checkpoint -> ADR author -> end; fails -> re-model
    # (until the cap) -> human checkpoint (WP25). The checkpoint pauses (interrupt) only when
    # something blocks sign-off — which a surviving validation error always does.
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            SOURCE_MAPPER_NODE: SOURCE_MAPPER_NODE,
            "dv2_modeler": "dv2_modeler",
            HUMAN_CHECKPOINT_NODE: HUMAN_CHECKPOINT_NODE,
        },
    )
    graph.add_edge(SOURCE_MAPPER_NODE, HUMAN_CHECKPOINT_NODE)
    graph.add_edge(HUMAN_CHECKPOINT_NODE, POST_VALIDATION_NODE)
    graph.add_edge(POST_VALIDATION_NODE, END)

    return graph
