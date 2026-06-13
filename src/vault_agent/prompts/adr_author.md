# adr_author agent

> This agent is deterministic and does not call an LLM; this file documents its behaviour.

## Role

Writes the single, publication-ready Architecture Decision Record that documents the chosen
Data Vault model and traces every construct back to the requirements that justify it. It is
the sole writer of `state.adrs`; it renders straight from `state.dv_model` (upstream agents
leave no draft fragments).

## Inputs

- `state.dv_model` — the typed hubs/links/satellites (the source of truth; each carries a
  description and `requirement_ids`).
- `state.requirements`, `state.business_keys`, `state.input_documents`,
  `state.artifacts` — for the ADR's context and references sections.

## Outputs

- `state.adrs` — replaced with the single finalized ADR markdown (status `Proposed`),
  following `docs/architecture/adrs/ADR-template.md`.

## Guardrails

- Render only what is in the model — no invented rationale or alternatives, so the
  architecture record is never subject to LLM hallucination.
- The ADR is `Proposed`: a human reviews and accepts it before it becomes authoritative.
- Constructs using specialised Data Vault types (transactional links, multi-active /
  effectivity satellites) are surfaced as a caveat for the reviewer.
