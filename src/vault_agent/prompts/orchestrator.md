# orchestrator agent prompt

> The orchestrator is **deterministic** — it makes no LLM call. This file documents its
> role for the architecture trail; there is no prompt to send. (Kept for parity with the
> multi-agent design, where every agent has a prompt entry.)

You are the **orchestrator** in the Vault-Agent pipeline.

## Role

Two jobs, both deterministic:

1. **Plan the run.** As the graph entry node you validate the inputs and record a typed
   `ExecutionPlan` (planned stages, declared input documents, whether source-schema
   grounding is active) so the run is observable from its first step.
2. **Collect the human-in-the-loop checkpoint.** After the pipeline finishes you assemble a
   categorized `HumanReviewQueue` from the run: validation errors/warnings, contracts still
   awaiting an owner, and the agents' review flags. This is the payload a human signs off on
   before the model and contracts are considered agreed.

## Inputs

- `state.input_documents`, `state.source_schemas` — to plan and validate the run.
- For the checkpoint: `state.validation_report`, `state.artifacts.contracts`, `state.errors`.

## Outputs

- `state.plan` — the `ExecutionPlan` (written by the entry node).
- The `HumanReviewQueue` — derived on demand from the finished state (surfaced by the CLI;
  written to `review-queue.md`). Not stored in state in this iteration.

## Guardrails

- Never invent or resolve a human decision: surface owners, errors, and flags for the human;
  do not assign owners or suppress issues.
- Blocking vs advisory: validation **errors** and unassigned **contract owners** block
  agreement; warnings and review flags are advisory.
- Live pause/resume (LangGraph `interrupt()` + checkpointer) is a planned follow-up
  (ADR-0006); for now the checkpoint is assembled and surfaced, not enforced as a halt.
