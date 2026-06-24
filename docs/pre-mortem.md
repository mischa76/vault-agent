# Pre-mortem & red-team — where this could fail, honestly

> **Purpose.** Adversarially surface the critiques a skeptical senior Data Vault practitioner /
> data architect would level at this project, *before* investing in the next phases — and answer
> each honestly, conceding where warranted. Written to find a showstopper cheaply if one exists,
> and to make the project's limits explicit rather than discoverable. **Snapshot: 2026-06-17.**
>
> Severity legend: **[NON-ISSUE]** stance is sound & honestly framed · **[VALUE-RISK]** real but
> empirical/answerable, not structural · **[SCOPE-GAP]** known, deferred, on the roadmap ·
> **[SHOWSTOPPER]** would invalidate the architecture.

## Bottom line (read first)

**No showstopper found.** The load-bearing decision — *assist + human ratifies + rules-as-code +
honestly-bounded scope* (ADR-0007) — means the system can't fail in the way that would actually
embarrass: it does **not** claim to automate business logic, discover truth from nothing, or
replace the architect. So there is no hidden structural assumption waiting to collapse.

The **real exposures** are three, and all are empirical/addressable, not architectural:

1. **Unproven on messy, real, multi-source input** — only toy single-source docs tested so far.
2. **No evals** — quality is asserted qualitatively, not measured.
3. **Value, not capability** — the architecture is sound; whether it saves a *DV-literate* human
   enough time to matter is unproven.

The antidote is not more idealized building — it's a reality test, an eval harness, and precise
framing. Each critique below ends with the concrete mitigation.

---

## A. Premise & value

**A1 — "You automated the cheap part." [VALUE-RISK]**
*Critique:* DV's Raw Vault is already pattern-based and cheap (that's why AutomateDV/VaultSpeed
exist). Generating hub/link/sat SQL adds little; the expensive work is upstream (source analysis,
scoping) and downstream (Business Vault rules, marts).
*Honest take:* Correct that Raw-Vault codegen *alone* is low-value. The value claim is the **front
door** — requirements → scoped model + business-key reasoning + data contracts + ADR trail +
grounding, transparent and human-gated — not the SQL. But this is exactly why the project must
**never lead with "generates dbt code."**
*Mitigation:* Headline = the entry point + governance + transparency. Treat codegen as the
*operability proof*, not the pitch.

**A2 — "Requirements documents that clean don't exist." [VALUE-RISK]**
*Critique:* Real Lastenhefte are contradictory, incomplete, 100s of pages, written by
non-technical stakeholders. The toy bank doc is unrealistically tidy.
*Honest take:* Valid — and the pipeline's behaviour on messy input is **untested**. The
HITL + gap-flagging + validator are *designed* for imperfect input ("surface what's missing"), but
whether the LLM degrades gracefully or produces confident nonsense is an open question.
*Mitigation:* The reality test (below) — run a deliberately messy, realistic doc and document
where it breaks. This is the single highest-value next experiment.

**A3 — "Business keys aren't discoverable from prose." [VALUE-RISK]**
*Critique:* In practice BK identification needs data profiling (uniqueness, nullability,
stability), tribal knowledge, and source archaeology — not a requirements sentence. Docs rarely
state the true BK.
*Honest take:* The sharpest critique of the front door. Today the BK identifier reads prose and
*proposes candidates with scores + flags ambiguity* — it never claims to "discover" the BK.
Source-schema grounding (Phase 1) is a first data-anchor; true profiling is deliberately deferred
(ADR-0007). 
*Mitigation:* Keep the framing strictly "candidate proposal, human ratifies." A profiling assist
(cardinality/uniqueness from a sample) is the highest-leverage future step to harden this.

---

## B. Data Vault methodology

**B1 — "One doc → one model ignores multi-source reality." [SCOPE-GAP]**
*Critique:* Real DV integrates many sources into shared hubs; the same concept arrives from five
systems with different keys, columns, and grain. The toy is single-source.
*Honest take:* The **primitives** are right and documented (hub keyed on BK + collision code;
per-source satellites — see how-requirements-become-a-model.md), but the pipeline has **not** been
exercised multi-source. Key harmonisation, collision codes, and "which source feeds which hub" are
largely design-on-paper.
*Mitigation:* Name multi-source explicitly as the enterprise shape and a future phase; don't imply
it's solved. A two-source variant of the demo would prove it.

**B2 — "You cover a fraction of DV constructs." [SCOPE-GAP]**
*Critique:* PoC = hub / link / standard sat / eff_sat. Deferred: multi-active sat, transactional /
self-referencing links, PIT, bridge, ref tables, XTS, hierarchical/same-as links.
*Honest take:* Honestly documented as deferred (PoC findings, spec §9). Still, that's most of the
construct zoo.
*Mitigation:* Keep the coverage table visible; grow by "add a type + a template + a test," never by
hacking heuristics (the generator is already built this way).

**B3 — "The hard/soft-rule line blurs in practice." [NON-ISSUE]**
*Critique:* Real Raw-Vault loads need light transforms (type harmonisation, splitting, dedup) that
muddy "no business logic in Raw Vault."
*Honest take:* Fair nuance, but the project is on the right side of doctrine and already locates
meaning-preserving technical normalisation in staging (how-requirements doc). Low risk.

**B4 — "Effectivity end-dating via clean snapshot batches is a simplification." [SCOPE-GAP]**
*Critique:* Real CDC/delta feeds, late-arriving data, and multi-active effectivity are messier
than the two-batch demo.
*Honest take:* True — the demo proves the *construct mechanism*, not production loading
orchestration.
*Mitigation:* Frame Phase B2 as "the eff_sat works and end-dates," not "loading is
production-grade."

---

## C. LLM / agentic

**C1 — "LLMs hallucinate; the modeling step isn't reproducible." [NON-ISSUE, well-mitigated]**
*Critique:* Two runs on the same doc yield different models; non-determinism is unacceptable for a
warehouse.
*Honest take:* Openly acknowledged (demo docs note the model varies per run). The architecture
**quarantines** non-determinism to the *proposal* stage: the validator (rules-as-code, independent
gate), the self-correcting loop, deterministic codegen, and HITL sign-off all sit downstream, and
the ADR trail makes the *accepted* model auditable. This is the correct design. Residual: the
modeling *decision* isn't reproducible run-to-run — acceptable because a human ratifies it.
*Mitigation:* Lead with "deterministic, human-gated downstream of an AI proposal."

**C2 — "No evals — quality is anecdotal." [VALUE-RISK, important]**
*Critique:* Without golden-sample measurement, "it works" is a vibe.
*Honest take:* Correct, and arguably the **most important missing piece** for a technical audience.
There is no quantitative quality measurement yet (LangSmith/evals deferred).
*Mitigation:* Build the eval harness *before* claiming real-world quality. A small golden set
(input doc → expected hubs/keys/links) with scored runs would convert assertions into evidence.

**C3 — "Cost / latency / context limits at real scale." [SCOPE-GAP]**
*Critique:* 100-page docs and large schemas hit context windows and cost.
*Honest take:* Untested; a real concern. Unaddressed.
*Mitigation:* Note as a known limit; chunking/retrieval is a future concern, not a claim today.

---

## D. Engineering & product

**D1 — "Single-author PoC, not production-hardened." [NON-ISSUE if framed]**
*Honest take:* True and openly an exploration. Only a risk if oversold. Keep the "working
exploration" framing.

**D2 — "AutomateDV lock-in / platform constraints." [NON-ISSUE]**
*Critique:* You're bound to AutomateDV's metadata model; you already hit DuckDB and the eff_sat
incremental quirk — more will come.
*Honest take:* A consciously recorded trade-off (ADR-0003). The constraints found so far were
handled and documented honestly. Bounded, not broken.

**D3 — "The staging layer is hand-authored — it's not a fully generated project." [SCOPE-GAP]**
*Critique:* A skeptic notices the demo's `stg_*` are hand-written (Finding #1). "Requirements →
runnable project" overclaims.
*Honest take:* Honestly documented as the #1 gap. The precise claim is "generates the **raw-vault
models**; staging is the next gap," not "generates a runnable project."
*Mitigation:* Use the precise wording everywhere; the staging generator is the natural next phase.

---

## E. Market & user

**E1 — "Incumbents are adding AI; you'll be outpaced." [NON-ISSUE]**
*Honest take:* Addressed in competitive-landscape.md — the moat is OSS + transparency +
requirements-entry + methodology, not a feature race. Window matters → ship visibly.

**E2 — "Who is the user?" [VALUE-RISK, sharp]**
*Critique:* The HITL needs a DV-literate human to ratify the output — so it only helps experts,
who are the ones least in need of codegen. A non-expert can't validate it.
*Honest take:* The honest answer: the value for an expert is **speed, toil reduction, and
auto-documentation**, not a capability they lack ("force multiplier, not replacement"). But the
*size* of that time-saving is unproven.
*Mitigation:* Validate with a real architect on a real doc; measure time-to-first-draft-model vs.
manual. That number is the actual product claim.

---

## What this changes (actions, in order)

1. **Reality test** — run the pipeline on a deliberately messy, realistic requirements doc;
   document where it breaks (A2, A3, B1). Cheapest, highest-signal de-risking.
2. **Eval harness** — a small golden set + scored runs (C2). Converts quality claims to evidence.
3. **Framing guardrails** (below) — eliminate the overclaim surface (A1, D3, E2).
4. *Then* Phase 2/3, informed by 1–3 rather than idealised.

## Framing guardrails — what to say, what never to claim

- **Lead with:** "transparent, methodology-grounded *assistant* for the requirements→Raw-Vault
  front door, with data contracts and an auditable decision trail." 
- **Never claim:** "generates a runnable warehouse project" (staging is hand-authored),
  "discovers business keys" (it proposes candidates), "automates Data Vault" (it assists the
  pattern-based layers and flags the rest), "production-ready" (it's an exploration).
- **Always show:** the deferred-construct table, the findings, and this pre-mortem. Openly named
  limits are credibility, not weakness — the audience you want punishes hidden overclaims, not
  honest scope.

## Verdict

The fear worth having is **overclaiming**, not a collapsing architecture. The structure holds; the
work is to *prove value empirically* and *frame precisely*. Do the reality test and the evals, keep
the honest framing, and there is nothing here a critic can surface that this document hasn't already
named — which is exactly the position you want to be in before going wide.
