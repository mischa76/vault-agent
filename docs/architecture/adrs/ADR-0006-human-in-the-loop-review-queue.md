# ADR-0006: Human-in-the-loop — a review queue plus live interrupt/resume

**Status:** Accepted
**Date:** 2026-06-14 (updated 2026-06-15: the deferred live-interrupt half landed)
**Decision makers:** Mischa Eismann

## Context

ADR-0002 chose LangGraph partly for its human-in-the-loop (HITL) support and committed to a
checkpointer for persistence. Several pipeline outputs now need human sign-off before a model
and its contracts can be considered *agreed*:

- contracts carrying a placeholder owner (the Data Contract agent never invents one, ADR-0005),
- validation issues the self-correcting loop could not resolve,
- the agents' accumulated review flags (undetermined types, missing source schema, column
  collisions, …).

The full LangGraph HITL mechanism — `interrupt()` plus a `SqliteSaver`/`PostgresSaver`
checkpointer — pauses a run mid-graph, persists state, and resumes it once a human supplies
input. That is real infrastructure: a checkpointer, resume semantics, a CLI `resume` command,
and a state-migration story. Building it before the *content* of the checkpoint is even
defined would be premature.

## Decision

Split HITL into **what** the human reviews (now) and **how** the run pauses (later).

**1. A deterministic review queue (now).** The orchestrator owns `assemble_review_queue`, a
pure function that derives a categorized `HumanReviewQueue` from a finished run:

- `validation_error` / `validation_warning` — one per `validation_report` issue, by severity.
- `contract_owner` — one per contract still holding the placeholder owner.
- `review_flag` — the remaining advisory flags from `state.errors` (owner flags are dropped,
  as they are already represented structurally as `contract_owner` items).

`requires_signoff` is true when any **validation error** or **unassigned contract owner** is
present — those block agreement; warnings and flags are advisory. The CLI prints the queue,
blocking-first, and writes it to `review-queue.md`. Being pure and deterministic, it is fully
unit-tested without an API key.

**2. The orchestrator becomes the graph entry node (now).** `START -> orchestrator -> …`, per
the multi-agent design topology. It validates inputs and records a typed `ExecutionPlan`
(planned stages, declared inputs, grounding on/off) so a run is observable from its first step.
It is deterministic — no LLM call.

**3. Live `interrupt()` + checkpointer + resume.** *(Implemented 2026-06-15.)* A
`human_checkpoint` node sits on the validated path (`validator --pass--> human_checkpoint
--> adr_author`). It assembles the queue and, when `requires_signoff`, calls LangGraph's
`interrupt()` to pause; `interrupt()` is the node's first statement, since the node
re-executes from the top on resume. The graph is compiled with a persistent
`AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`) keyed by a per-run `thread_id`, stored
under `<out>/.vault-agent/`. The CLI splits into two commands: `run` detects the
`__interrupt__`, writes the artifacts produced so far plus a `pending.json` pointer, and
prints how to resume; `resume` reads the pending thread, builds the decision from
`--owner "asset=Name <email>"` / `--accept`, and continues the same thread with
`Command(resume=…)`. On resume `apply_human_decision` writes the owners onto the contracts
and prunes the now-resolved owner flags, then the ADR author finalizes. As predicted, the
checkpoint *content* (section 1) was reused verbatim — only the delivery mechanism was
added. The checkpointer's serializer is configured with an allow-list of the state models
so checkpoints round-trip without LangGraph's "unregistered type" deprecation warning.

## Alternatives considered

- **Build full `interrupt()` + checkpointer now** — rejected for this iteration: heavy infra
  (persistence, resume semantics, CLI `resume`, migrations) ahead of a defined checkpoint
  payload. The split lets each half land cleanly; the deferred half reuses this one verbatim.
- **Keep dumping raw `state.errors`** (the prior CLI behaviour) — rejected: an undifferentiated
  flag list does not distinguish blocking from advisory, nor surface contracts awaiting an
  owner as actionable items. The categorized queue does.
- **Store the queue in `state`** — not needed yet: it is derived on demand from the finished
  state. When the live interrupt lands it will populate state at the checkpoint node; until
  then keeping it out of state keeps the stored state to inputs and produced artifacts only.

## Consequences

- (+) A clear, categorized HITL checkpoint surfaced in the CLI and persisted to
  `review-queue.md`; blocking vs advisory is explicit.
- (+) The orchestrator is no longer a stub: it plans the run and is the structural home for
  HITL, matching the design topology and ADR-0002.
- (+) Deterministic and key-free, so it is covered by unit tests like the other agents.
- (+) *(2026-06-15)* The run now genuinely halts at the checkpoint and resumes from a
  separate process via the SQLite checkpointer, so a human assigns contract owners between
  `run` and `resume` and the pipeline finalizes only after sign-off.
- (neutral) Resume is driven by CLI flags (`--owner`, `--accept`), not yet an interactive
  prompt or UI; sufficient for the CLI-first workflow.
- (-) Some coupling: the queue filters owner flags by a marker string shared with the Data
  Contract agent; the placeholder-owner literal is centralized on `ContractOwner.PLACEHOLDER_NAME`
  to keep one source of truth.

## References

- Orchestration framework and HITL commitment: ADR-0002
- Data contract spec and the placeholder-owner rule: ADR-0005
- Multi-agent design (graph topology, Orchestrator at START):
  `docs/architecture/2-multi-agent-design.md`
- LangGraph HITL / persistence (the deferred half): https://langchain-ai.github.io/langgraph/
