# Architecture overview

## Layered view

```
+---------------------------------------------------------------+
|  Input layer:  PDF/DOCX/MD requirements   SQL/DDL schemas      |
+---------------------------------------------------------------+
|  Orchestration:  LangGraph supervisor + subgraphs              |
+---------------------------------------------------------------+
|  Agents:                                                       |
|    Requirements Parser   Business-Key Identifier               |
|    DV2.0 Modeler         Code Generator                        |
|    Data Contract         Validator                             |
|    ADR Author            Orchestrator                          |
+---------------------------------------------------------------+
|  Tool layer (MCP):  Schema Inspector  PDF Reader               |
|                     AutomateDV Writer  dbt Parser              |
+---------------------------------------------------------------+
|  Backends:  AutomateDV + dbt Core                              |
|  Targets:   Snowflake / MS Fabric / PostgreSQL (demo)          |
+---------------------------------------------------------------+
|  Observability:  LangSmith traces + evals                      |
+---------------------------------------------------------------+
```

## State model

A single pydantic `VaultAgentState` is passed through the graph. Each agent reads the
fields it needs, writes the fields it owns. No shared mutable state outside of this.

## Persistence

LangGraph checkpoints to disk (sqlite for local, optional postgres for production demo)
so a long pipeline can be resumed and intermediate state can be inspected.

## Human-in-the-loop

The orchestrator pauses when:
- multiple business-key candidates score within 10% of each other
- the validator finds DV2.0 rule violations the modeler couldn't fix
- a generated artifact would overwrite existing user-modified files
