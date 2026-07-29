# ADR-0010: Modeler output scaling — streaming before staged modelling

**Status:** Accepted (2026-07-29)
**Date:** 2026-07-29
**Decision makers:** Mischa Eismann

## Context

The DV2.0 modeler emits ONE coherent model as a single forced tool call. Its output is
the only one in the pipeline that cannot be split: the four list-shaped agents
(requirements, business keys, contracts, mapping) share `llm.call_with_truncation_split`,
but merging two half-models is a modelling problem, not a dedup problem — a link can span
the halves, a hub proposed in both must be reconciled, a satellite's parent can sit on
the other side (recorded 2026-07-28, output-budget hardening).

Measured output growth (from replayed traces, not guessed): 30 source tables → 7,225
output tokens; 100 tables → 13,889 isolated / 14,981 in-pipeline — sub-linear (3.3×
tables → ~1.9× tokens), extrapolating to **~26k tokens at 300 tables**. The current
budget is `_MAX_TOKENS = 16384`, deliberately called a stopgap: it is the ceiling that is
safe WITHOUT streaming (the shared `ForcedToolCaller` is non-streaming, and non-streaming
requests risk HTTP timeouts above roughly that size), and the 100-table case already sits
at 91% of it. 300 tables therefore does not fit today's transport. Two candidate answers
were recorded: streaming in `ForcedToolCaller`, or staged modelling (hubs, then links,
then satellites). This ADR compares them and decides the order.

Constraints that shape the decision:

- The **coherence property is the modeler's core quality property**: every steering rule
  (16 in the WP16 registry), the validation re-model loop, the eval scorers, and both
  demo walkthroughs assume one model emitted in one pass, where the model can trade off
  hubs against links against satellites while deciding.
- The scale axis is **verified at 30 tables only**; scale_100 has never completed
  end-to-end. The 300-table target is a robustness goal (Charter A), not a proven
  customer workload.
- House rule: prefer the cheap, reversible change that meets the *measured* need; pay
  for architecture only when a measurement says the cheap lever is exhausted.

## Decision

**Adopt streaming in `ForcedToolCaller` now (Option A). Defer staged modelling (Option
B) until a measurement shows streaming's limits** — either a landscape whose coherent
model exceeds the configured model's output-token limit, or eval evidence that very long
single emissions degrade model quality. Do not build B speculatively.

## Alternatives considered

### Option A — Streaming in `ForcedToolCaller` (chosen)

Replace the non-streaming `messages.create` with the SDK's streaming path, accumulate
the final message (tool-input JSON deltas → same payload shape), keep everything else —
forced tool choice, retry/backoff, truncation detection (`stop_reason == "max_tokens"`
on the final message), usage capture, trace events — identical.

*Pros:*
- **One change point, every agent benefits** — the same reason WP2/P2 centralised the
  call path in the first place. No agent, prompt, graph, state, or eval change.
- **No modelling-quality risk.** The model still sees the whole problem and emits one
  coherent model; the coherence property is untouched by construction.
- Removes the *transport* ceiling entirely; `_MAX_TOKENS` can rise to the model's output
  limit. Current Claude generations sit in the tens of thousands of output tokens
  (verify the exact limits for the configured `heavy_model` against the live docs — the
  t_link lesson applies), so the extrapolated ~26k at 300 tables fits with margin.
- Fully testable keyless: the injectable stub client mimics the stream (or the stream
  helper's `get_final_message()`), all existing `tests/test_llm.py` semantics carry over.
- Reversible and non-foreclosing: streaming is also the transport staged modelling would
  want, so nothing built here is thrown away if B ever lands.

*Cons / risks:*
- Does not reduce cost or latency: one giant generation decodes sequentially, and a
  failure at token 25k costs the whole call — the truncation-split cannot help a
  single-artefact output. Retries of a ~26k-token emission are expensive.
- Possible quality drift on very long single emissions (consistency over one huge JSON).
  Unproven either way — exactly what the scale_100/300 eval runs should measure once the
  transport no longer fails first.
- Lifts the transport ceiling, not the model ceiling: somewhere past the extrapolated
  range a coherent model stops fitting any single response. Streaming buys the measured
  target (300 tables) — not unbounded scale.

### Option B — Staged modelling (hubs → links → satellites)

Split the modeler into sequential stages, each a bounded forced call: emit hubs; emit
links given the hubs; emit satellites given hubs + links. Satellites — the bulk of the
output — become list-shaped once their parents are fixed and could even reuse the
truncation split.

*Pros:*
- Genuinely unbounded in landscape size; each stage's output is small and the satellite
  stage is splittable with the existing, proven mechanism.
- Cheaper failures: a stage retry re-pays only that stage; validation feedback could
  target the failing stage instead of re-modelling everything.
- Focused per-stage prompts may steer better than one 16-rule prompt.

*Cons / risks:*
- **Re-introduces the merge problem as a staging problem.** The stages are coupled in
  both directions: deciding links can reveal that a "hub" is really a relationship
  (`no_object_link_confusion`), satellite splitting can argue for a different link grain
  — a staged modeler cannot revise an earlier stage without a revision loop, i.e. worse
  models or a new orchestration layer. This is the same reason half-model merging was
  rejected, moved one level up.
- Large blast radius: modeler node becomes a subgraph (graph.py, MAX_MODELING_ATTEMPTS
  semantics, retry feedback routing), the WP16 steering registry must be re-partitioned
  per stage (prompt re-engineering with re-measurement — the registry's byte-identity
  and ablation machinery all assume one prompt), traces/evals/scorers need new shapes.
  Realistically spike + L-sized WP + full eval re-baseline against both demos.
- Higher token cost per run (hubs + links context re-sent per stage; prompt caching
  softens but does not remove it).
- All of that spent before knowing whether the quality of long single emissions is even
  a problem — architecture bought on an unmeasured fear.

### Option C — Domain partitioning of the input (noted, not scored)

The long-term product answer at true enterprise scale is neither A nor B: nobody models
300 tables as one undifferentiated pass. Partition the *input* by business domain, model
each domain coherently, and integrate across domains via the existing multi-source-hub
machinery (WP10) plus same-as handling (deferred). This is a product/methodology feature
with its own HITL surface, not a transport fix — out of scope here, recorded so the
staged-modelling discussion does not resurface as its accidental substitute.

## Consequences

- Positive: 300-table landscapes become *attemptable* with a small, reversible,
  centrally-tested change; every other agent inherits the higher ceiling for free; the
  scale_100/300 measurement protocol (which today dies at the transport) can finally
  produce the numbers that would justify — or bury — Option B.
- Negative: single-call cost/latency at 300 tables is real (~26k output tokens per
  modeling attempt, retries included); quality of very long emissions remains unmeasured
  until the runs happen.
- Neutral: `_MAX_TOKENS` moves from "non-streaming ceiling" to a deliberate budget just
  under the configured model's output limit, with the same truncation semantics; the
  stopgap comment in `dv2_modeler.py` is replaced by a pointer to this ADR.
- Follow-up trigger (records the exit condition): open the staged-modelling / domain-
  partitioning discussion when EITHER a required landscape's coherent model exceeds the
  configured model's output limit, OR the scale evals show construct quality degrading
  with emission length at unchanged inputs.

## Implementation note (2026-07-29, WP22)

Implemented. Two numbers this ADR reasoned about are now verified rather than estimated:

- **The non-streaming ceiling was never "roughly 16k".** The installed SDK raises
  `ValueError("Streaming is required for operations that may take longer than 10
  minutes")` when `3600 * max_tokens / 128_000 > 600` — i.e. above **21,333** output
  tokens (plus a per-model table that does not list `claude-opus-4-8`). 16384 was
  conservative, but the decision it forced was the right one.
- **The model ceiling is 128,000 output tokens** for `claude-opus-4-8`, confirmed against
  the live Models API, not from memory.

The modeler budget went to **32768**, not to the model maximum: it clears the ~26k
300-table extrapolation with ~26% headroom while keeping a runaway generation's cost
bounded. The exit condition stands unchanged — a model needing more than that is a case
for staged modelling / domain partitioning, not another budget bump.

## References

- CLAUDE.md milestone "Output-budget hardening" (2026-07-28): the measured token table,
  the two output shapes, and the 16384 stopgap rationale.
- `docs/architecture/backlog-2026-07/wp13-scale-hardness-spec.md` (Charter A scale axis),
  `wp16-steering-retest-spec.md` (registry/ablation machinery Option B would touch).
- `src/vault_agent/llm.py` (`ForcedToolCaller`), `src/vault_agent/agents/dv2_modeler.py`
  (`_MAX_TOKENS` comment this ADR supersedes).
- Anthropic SDK streaming helpers (verify against the installed SDK before
  implementation — the WP8 t_link lesson).
