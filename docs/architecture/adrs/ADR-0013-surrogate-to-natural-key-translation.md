# ADR-0013: Surrogate→natural-key translation for FK-derived link proposals

**Status:** Proposed
**Date:** 2026-08-14
**Decision makers:** Mischa Eismann

## Context

The 2026-08-12 audit of WP34's declined foreign keys (`docs/log.md`, "The remaining 22 audited")
isolated one real capability gap. Of 22 declined FKs on AdventureWorks, 18 reference a table from
their own increment — the modeler's job by design, graph order is load-bearing — and **4 are one
case**: the source declares referential integrity on a **surrogate** (`Product.ProductID`), while
the vault hub is keyed on the **natural business key** (`hub_product` on `ProductNumber`), which
is the choice DV2.0 doctrine asks for and the source's own column comments endorse.

Neither side is wrong, and that is the problem: an FK-derived proposer that matches on the hub's
business key can never bridge the two. Bridging means **translating the surrogate to the natural
key through the referenced relation** — a join through a third table and a real modelling
operation, not an alias or a rename (the audit explicitly rejects smuggling it in as one).

Stakes, pre-registered before any spend: WP34 §6's link clause needs ≥ 8 cross-domain links; the
binder fix alone predicts ~5, surrogate translation adds the 4 → ~9. The bar is reachable only
with this capability — or the bar is wrong. This ADR decides which.

**A caveat inherited from the audit:** `hub_product` keyed on `ProductNumber` is one run's
modelling choice. Doctrine makes it likely, not guaranteed; a run that keys the hub on
`ProductID` turns all four cases into ordinary proposals with no new capability needed.

## Decision (proposed)

Build surrogate→natural-key translation into the link proposer and staging path, bounded as
follows:

1. **Trigger, deterministic.** An FK references column `X` of relation `R`; a hub bound to `R`
   exists and is keyed on column `Y ≠ X`; `R` declares both `X` and `Y`. No LLM judgement in the
   trigger.
2. **Mechanism.** The proposed link's staging derives the link's hash inputs by joining through
   `R` on `X` to project `Y` — the translation is visible in generated dbt code, not hidden in a
   mapping. Key-column resolution goes through the `rules/` helpers
   (`canonical_hub_key_column` et al.), never re-derived locally.
3. **HITL, typed.** Each translated proposal carries a distinct typed marker (extend
   `FlagKind`/the proposal type — branch on typed fields, never message text) so the checkpoint
   shows *"this link required surrogate translation through `R`"* as its own review class.
4. **Guards before change.** Byte-identity fixtures for existing greenfield/ungrounded output
   are committed first; the capability must be provably additive. The deterministic core is
   testable keyless against the recorded WP34 shapes in `eval/results/`.

## Alternatives considered

- **Do nothing; revise §6's bar down to what the proposer can reach (~5).** Honest but weak: the
  4 declines are not noise, they are the enterprise-normal case — sources reference surrogates,
  vaults key on natural keys. Every brownfield landscape with generated PKs will hit this.
  Declining it structurally caps what incremental mode can ever propose.
- **Key hubs on the surrogate when sources reference it.** Rejected. It would dissolve the
  conflict by abandoning the natural-business-key doctrine the modeler currently gets right —
  and ADR-gating a DV2.0 deviation to save a proposer is the tail wagging the dog.
- **Treat it as an alias/same-as mapping.** Rejected by the audit: the translation is a join
  through a third relation with its own failure modes (unmatched surrogates, multi-row), not a
  rename. Modelling it as an alias would hide exactly the operation a reviewer must see.
- **Let the modeler handle it (extend its scope to cross-increment FKs).** Rejected: the modeler
  sees one increment; giving it cross-increment reach reorders responsibilities the graph
  deliberately separates, and duplicates the proposer's mandate.

## Consequences

- (+) The 4 audited cases become proposals; §6's conjunction becomes testable at its
  pre-registered bar (~9 ≥ 8) instead of being unreachable by construction.
- (+) The capability is enterprise-relevant beyond AdventureWorks (surrogate-referencing
  sources are the norm in exactly the DACH landscapes the project targets).
- (−) New staging join pattern = new failure surface: unmatched surrogates and duplicate `Y`
  values need a deterministic gate or an explicit flag, decided in the spec (gate refuses vs.
  backstop repairs — pick one per the invariant).
- (−) Effectiveness depends on the modeler continuing to choose natural keys (see caveat).
  The spec must include the counter-case: if a run keys the hub on the surrogate, the trigger
  simply never fires — the capability must be a no-op then, not a wrong join.
- (neutral) WP30's arm-B rerun should wait for this decision: with the capability, the rerun
  measures the full mechanism; without it, the rerun measures a state known to sit below §6's
  bar. Either is a legitimate experiment — but which one we are running must be decided before
  paying, not read off afterwards.

## References

- `docs/log.md` 2026-08-12, "The remaining 22 audited: 18 are by design, 4 are a design question"
- WP34 spec §3.2 (proposer conditions), §6 (pre-registered conjunction):
  `../backlog-2026-07/wp34-fk-derived-link-proposals-spec.md`
- ADR-0011 (satellite source binding), ADR-0009 (role-qualified references) — the existing
  patterns the staging change must compose with
- Invariants: guard-before-change, typed-field branching, helpers in `rules/` (CLAUDE.md)
