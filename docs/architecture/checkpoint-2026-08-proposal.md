---
type: charter
status: proposed
---

# Checkpoint 2026-08 — a named "clean state", and the WP34 bar re-derived

Status: **Proposed** (drafted Cowork 2026-08-12, decision: Mischa). If ratified, the decision
becomes a dated `docs/log.md` entry and this document is the record it points to.

## Why this document exists

The project has pre-registered bars per work package but no named criterion for the project
state itself. The result is that "are we close to a good, clean state?" is currently
unanswerable — *clean by which standard?* This charter fixes that by (a) re-deriving WP34 §6's
link bar from the 2026-08-12 audits, **before** the next paid run, and (b) naming the exit
criteria for a checkpoint state. Both are pre-registrations, not post-hoc adjustments: the
numbers below were put on record in `docs/log.md` (2026-08-12, three entries) prior to any run
that will be judged against them.

## Part A — WP34 §6 link clause, re-derived

The original clause (≥8 cross-domain links) was set against a supply of 16 schema-crossing
foreign keys. The 2026-08-12 audits showed that supply was wrong twice over:

1. **18 of the 22 `no_hub_for_key` skips are structural**: the referenced table is first
   declared in the proposer's own increment, so no hub can exist at proposal time. Graph order
   is load-bearing; these are the modeler's job and were never in the proposer's reach. They
   should not have been counted as supply (log, 2026-08-12, "The remaining 22 audited").
2. **4 skips are one design question**: sources reference `Product.ProductID` (surrogate),
   `hub_product` is keyed on `PRODUCTNUMBER` (the natural key — correctly, per DV2.0).
   Bridging them is surrogate→natural key translation through the referenced relation: a new,
   ADR-shaped capability, explicitly **not** in WP34 §3.2's conditions.

Honest supply after the binder fix (`cb01b9c`), recomputed offline against the recorded
shapes: **9 proposals, of which 5 find a near hub** — an upper bound before
grain-deduplication (log, 2026-08-12, "The missing links were a separator").

**Re-derived clause, proposed:** the next `adventureworks_incremental` run must produce
**≥ 4 applied cross-domain links** (prediction on record: ~5; the one-link allowance covers
grain-deduplication, which the offline replay cannot see). The joins clause stands unchanged
(0 unsound aliases, 0 `E_LINK_KEY_NOT_IN_SOURCE`). The **review-load clause is dropped from
judgement at n=1**: the 2026-08-12 pair (546 vs. 833 on identical inputs) is direct evidence
that this axis cannot carry a conclusion from a single run.

The ≥8 bar is not deleted — it is recorded as *reachable only with surrogate→natural key
translation* (5 + 4 = 9), and that capability goes to an ADR, not into WP34. Caveat already
on record: the 4 depend on the modeler continuing to key `hub_product` on the natural key,
which is one run's behaviour.

## Part B — Checkpoint exit criteria

The checkpoint is reached when all five hold. Estimated spend: **one paid run (~$9)**;
everything else is keyless or a zero-cost trace audit.

| # | Criterion | Cost | Judged by |
|---|---|---|---|
| 1 | Binder fix live-verified: one `adventureworks_incremental` run meets the re-derived clause (Part A) | ~$9 | `wp34_check` with the re-derived clause, committed before the run |
| 2 | WP29 §4 unblocked keyless: `brownfield_resolution` has `dataset.yml`, requirements, scorer dispatch; `false_merge_rate` matches on `entity::field` keys | 0 | `uv run pytest`, green without a key |
| 3 | `E_HUB_HK_COLLISION` ×3 (run `c238abc`) explained from the stored traces, or recorded as a known issue with the trace excerpt quoted | 0 | log entry citing tool name and attempt |
| 4 | WP30 formally parked: dated entry stating all arm-B evidence pre-`cb01b9c` is void, a repeat requires n≥2 per arm, with the cost estimate on record | 0 | the entry exists; repeat is **not** a checkpoint blocker |
| 5 | WP34 closed or re-scoped by dated entry per Part A; the 4 surrogate-key cases spun off as an ADR candidate | 0 | the entry exists |

**Explicitly out of scope** (open, named, not blockers): `scale_300`, WP18 acceptance #1,
surrogate→natural key translation, stage-2 HITL web UI, the WP30 repeat itself.

## What the checkpoint claims when green

Greenfield end-to-end: live-verified. Brownfield: mechanism live-verified (checkpoint
steering, FK-derived proposals, alias projection), with its limits named — proposer reach
ends at the increment boundary by design, surrogate-keyed references are a known gap, scale
verified to ~30 tables of real semantic variety. Plus a known-issue list instead of silence.
That is a state one can show a client without a footnote contradicting it.

## After the checkpoint — the fork to decide then, not now

Option 1: build the surrogate-translation ADR (deepens brownfield). Option 2: spend the next
block on the adoption path (demo hardening, mandate material) — the roadmap addendum names
consultant-embedded adoption as the critical path, and no current WP serves it. This charter
deliberately does not decide the fork; it only ensures the decision is made from a named,
clean state.
