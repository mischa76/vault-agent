# Architecture overview

## Layered view

```
+--------------------------------------------------------------+
|  Input layer:  PDF/DOCX/MD requirements                      |
|                declared source schema (YAML/JSON) + profiling|
+--------------------------------------------------------------+
|  Orchestration:  LangGraph state machine + HITL checkpoint   |
+--------------------------------------------------------------+
|  Agents:                                                     |
|    Orchestrator          Requirements Parser                 |
|    Business-Key Ident.   Data Contract                       |
|    DV2.0 Modeler         Code Generator                      |
|    Validator             Source Mapper                       |
|    ADR Author            Human Checkpoint                    |
+--------------------------------------------------------------+
|  Backends:  AutomateDV + dbt Core                            |
|  Targets:   Snowflake & MS Fabric (focus); any AutomateDV DB |
+--------------------------------------------------------------+
|  Observability:  LangSmith traces + evals                    |
+--------------------------------------------------------------+
```

(Anthropic MCP is the intended typed tool-integration surface; no tool registry has landed
yet — the agents read documents and emit artifacts through typed I/O directly.)

## State model

A single pydantic `VaultAgentState` is passed through the graph. Each agent reads the
fields it needs, writes the fields it owns. No shared mutable state outside of this.

## Persistence

LangGraph checkpoints to disk (sqlite for local, optional postgres for production demo)
so a long pipeline can be resumed and intermediate state can be inspected.

## Human-in-the-loop

The `human_checkpoint` node (ADR-0006) assembles a categorized review queue and pauses the run
(LangGraph `interrupt()`) only when sign-off is blocked — i.e. `requires_signoff` is true:

- a validation error remains after the re-model budget is exhausted, or
- a data contract still has no assigned owner.

Coverage gaps from the source mapper and other advisory findings surface in the queue but do
not block. `vault-agent resume` continues the same run from the persisted checkpoint once the
human assigns owners / ratifies mappings / accepts.
