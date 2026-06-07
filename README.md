# Vault-Agent

> Agentic AI for Data Vault 2.0 automation – multi-agent system that turns business
> requirements and source schemas into compliant DV2.0 models, AutomateDV-generated
> dbt code, and runtime data contracts.

**Status:** Early development (W1 of 12-week build).

## Why this exists

The intersection of classical DWH/Data-Vault practice and modern Agentic AI is a niche
with very few competent players. Vault-Agent automates the repetitive, error-prone
parts of DV2.0 modeling – business-key identification, hub/link/satellite generation,
contract creation – while keeping the discipline of the DV2.1 methodology and the
Data Solutions Architecture Framework (Roelant Vos).

## What's inside

Eight specialized agents orchestrated in LangGraph:

1. **Requirements Parser** – extracts entities, relationships, business rules from documents
2. **Business-Key Identifier** – evaluates key candidates against DV2.0 heuristics
3. **DV2.0 Modeler** – generates Hubs, Links, Satellites under DV2.1 rules
4. **Code Generator** – emits AutomateDV-compatible YAML + dbt models
5. **Data Contract Agent** – generates source-to-staging contracts
6. **Validator** – checks generated artifacts for compliance
7. **ADR Author** – documents architectural decisions made by the agents
8. **Orchestrator** – plans agent order, handles human-in-the-loop steps

## Quick start (will work after first implementation milestone)

```bash
git clone https://github.com/<your-org>/vault-agent.git
cd vault-agent
uv sync
cp .env.example .env  # then add ANTHROPIC_API_KEY
uv run python examples/01_simple_requirement.py
```

## Documentation

- [Vision](docs/architecture/0-vision.md)
- [Architecture overview](docs/architecture/1-architecture-overview.md)
- [Multi-agent design](docs/architecture/2-multi-agent-design.md)
- [Architecture Decision Records (ADRs)](docs/architecture/adrs/)
- [DV2.0 rules cheatsheet](docs/methodology/dv2-rules-cheatsheet.md)

## License

MIT – see [LICENSE](LICENSE).
