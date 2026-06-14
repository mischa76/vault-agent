# ADR-0002: Orchestration framework = LangGraph

**Status:** Accepted
**Date:** 2026-06-07
**Decision makers:** Mischa Eismann

## Context

Multi-agent systems need: typed state, conditional routing, persistence/checkpoints,
human-in-the-loop, and observability. The choice shapes how agents are composed.

## Decision

Use LangGraph as the orchestration framework. State is a single pydantic `VaultAgentState`
model. Agents are nodes. Conditional edges express routing. Sqlite checkpointer for local
development, postgres optional for hosted demos.

## Alternatives considered

- **crewAI** – higher level, opinionated about roles; less control over state and routing
- **AutoGen** – conversation-centric; harder to express deterministic pipelines
- **Custom (Pydantic state machine + asyncio)** – maximum control but reinvents tooling
  for checkpointing, tracing, and HITL

## Consequences

- (+) Native LangSmith tracing for free
- (+) Subgraph pattern fits the agent-of-agents architecture
- (+) Active community and rapid iteration
- (-) Library churn risk – pin versions and lock with uv

## References

- LangGraph docs: https://langchain-ai.github.io/langgraph/
