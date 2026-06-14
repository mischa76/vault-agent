# Multi-Agent Design

For each agent: responsibility, inputs, outputs, tools, prompt location, and the field(s)
of `VaultAgentState` it owns.

| Agent | Owns | Tools | Prompt |
|---|---|---|---|
| Requirements Parser | `state.requirements` | PDF Reader, JSON Schema Writer | prompts/requirements_parser.md |
| Business-Key Identifier | `state.business_keys` | Schema Inspector, Data Profiler | prompts/business_key.md |
| DV2.0 Modeler | `state.dv_model` | DV Rules Validator | prompts/dv_modeler.md |
| Code Generator | `state.artifacts.automatedv_yaml`, `state.artifacts.dbt_models` | AutomateDV Writer, dbt Parser | prompts/code_generator.md |
| Data Contract | `state.artifacts.contracts` | Contract Schema Writer | prompts/data_contract.md |
| Validator | `state.validation_report` | AutomateDV Validator, dbt parse | prompts/validator.md |
| ADR Author | `state.adrs` | Markdown Writer | prompts/adr_author.md |
| Orchestrator | execution plan | LangGraph subgraph manager | prompts/orchestrator.md |

## Graph topology

```
START -> Orchestrator -> RequirementsParser -> BusinessKeyIdentifier
                                                    |
                                                    v
                                              DV2.0 Modeler
                                                    |
                                                    v
                                          CodeGenerator + DataContract
                                                    |
                                                    v
                                               Validator
                                                    |
                                                    v
                                             ADR Author -> END
```

Decisions, retries, human checkpoints are inserted by the Orchestrator as conditional edges.
