# Multi-Agent Design

For each agent: the field(s) of `VaultAgentState` it owns, whether it is LLM-backed or
deterministic, and its prompt (LLM agents only — the deterministic agents carry no prompt).

| Agent | Owns (`VaultAgentState`) | Kind | Prompt |
|---|---|---|---|
| Orchestrator | `state.plan`; assembles the HITL review queue | deterministic | — |
| Requirements Parser | `state.requirements` | LLM | prompts/requirements_parser.md |
| Business-Key Identifier | `state.business_keys` | LLM | prompts/business_key_identifier.md |
| Data Contract | `state.artifacts.contracts`, `state.artifacts.dbt_tests` | LLM enricher + deterministic core | prompts/data_contract.md |
| DV2.0 Modeler | `state.dv_model` | LLM | prompts/dv2_modeler.md |
| Code Generator | `state.artifacts.{automatedv_yaml, dbt_models, staging_models, scaffolding}` | deterministic | — |
| Validator | `state.validation_report` (32 E_/W_ gates) | deterministic | — |
| Source Mapper | `state.mappings` (business↔source, ADR-0008) | LLM proposer + deterministic core | prompts/source_mapper.md |
| ADR Author | `state.adrs` | deterministic | — |

A `human_checkpoint` node (ADR-0006) sits between the source mapper and the ADR author; it
assembles the review queue and pauses the run (LangGraph `interrupt()`) only when sign-off is
blocked. Agent findings flow through typed `state.flags` (`list[PipelineFlag]`), not a
stringly-typed error channel.

## Graph topology

```
START -> Orchestrator -> Requirements Parser -> Business-Key Identifier -> Data Contract
                                                                                |
                                                                                v
                                                     +--------------------> DV2.0 Modeler
                                                     |                          |
                                                fail | (re-model,               v
                                                     |  max 3 attempts)   Code Generator
                                                     |                          |
                                                     |                          v
                                                     +--------------------- Validator
                                                                                | pass
                                                                                v
                                                                          Source Mapper
                                                                                |
                                                                                v
                                                              Human Checkpoint (HITL: interrupt / resume)
                                                                                |
                                                                                v
                                                                           ADR Author -> END
```

The data contract runs before modeling on purpose: it describes source-to-staging assets, so
it depends only on the requirements, business keys, and (optional) source schema — not the DV
model — and is therefore never re-run by the validation re-model loop. On a validator failure
the run routes back to the DV2.0 modeler with the issues as feedback, bounded by
`MAX_MODELING_ATTEMPTS` (3); on success it proceeds to the source mapper (which runs once, on
the now-stable model), the human checkpoint, and the ADR author. If the retry budget is
exhausted the run ends without finalizing.
