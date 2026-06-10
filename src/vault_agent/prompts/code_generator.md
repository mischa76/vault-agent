# code_generator agent

> This agent is deterministic and does not call an LLM; this file documents its behaviour.

## Role

Renders the logical Data Vault model in `state.dv_model` into AutomateDV-compatible dbt
models. The typed Hub / Link / Satellite constructs map 1:1 onto AutomateDV macro
arguments (ADR-0003), so generation is reproducible and runs without an API key.

## Inputs

- `state.dv_model` — the hubs, links, and satellites to render.

## Outputs

- `state.artifacts.dbt_models` — one dbt model (`{{ automate_dv.<macro>(...) }}`) per
  generated construct.
- `state.artifacts.automatedv_yaml` — a machine-readable metadata summary of the macro
  arguments per construct.

## Dispatch (construct type -> AutomateDV macro)

| Construct | Type | Macro |
|---|---|---|
| Hub | — | `automate_dv.hub` |
| Link | `standard` | `automate_dv.link` |
| Link | `transactional` | `automate_dv.nh_link` (needs `event_timestamp`) |
| Satellite | `standard` | `automate_dv.sat` |
| Satellite | `multi_active` | `automate_dv.ma_sat` (needs `child_dependent_key`) |
| Satellite | `effectivity` | `automate_dv.eff_sat` (parent must be a link; needs start/end dates) |

## Guardrails

- A construct that cannot be generated correctly (unknown parent, multi-active without a
  child dependent key, effectivity satellite not on a link, transactional link without an
  event timestamp) is flagged for human review rather than emitted as wrong SQL. Coverage
  grows by adding a type on the model plus a template — never by hacking heuristics into
  the generator.
