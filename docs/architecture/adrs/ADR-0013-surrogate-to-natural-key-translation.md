# ADR-0013: Surrogate→natural-key translation for FK-derived link proposals

**Status:** Accepted (2026-09-12, Mischa Eismann — option "accept, build, then rerun" over
"defer and rerun the binder fix alone", "both reruns" and "reject and lower the bar"; the
build is WP36, the paid rerun follows it per the WP30 rerun protocol)
**Date:** 2026-08-14 (proposed) · 2026-09-12 (accepted)
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


## Note appended 2026-10-31 — the review class is one decision per key (WP116)

§3's „its own review class" was built as one **decision** per translated link (WP36) and per translated
satellite (WP38), kept individual by WP43's amendment. The C1 finding of 2026-10-31 (`docs/log.md`) showed what
that costs: 60 decisions for 21 relations on one chain, each repeating the question a ratified key licence or
proposal had answered — and the gates `E_LINK_TRANSLATION_UNRATIFIED`/`E_SAT_TRANSLATION_UNRATIFIED` admit no
other. WP116 (`backlog-2026-07/wp116-translation-ratified-per-key-spec.md`) keeps the class and changes its unit:
the per-construct flags are disclosures grouped by the key they translate to, and the decision is one per key
(hub, relation joined through, natural key), the confirmation of the generated translation model asked once. The
reviewer still sees every join; §3's reasoning stands, the counting is corrected. The ADR's text stays as drafted.


## Note appended 2026-11-14 — the caveat came true; a translation over a declared key becomes a disclosure (ADR-0021)

The caveat this ADR inherited from the audit — that `hub_product` on `ProductNumber` was one run's choice and that
the capability's effectiveness „depends on the modeler continuing to choose natural keys" — came true with the 5.5
models: the chains since 2026-10-09 key `hub_product` and most other hubs on the generated primary key, the
alternative this ADR rejected by name, and the translation had almost no cases (C63, `docs/log.md` 2026-11-14).
ADR-0021 takes the key out of the modeler's discretion; the translation therefore returns as the ordinary case.

On the owner's go (2026-11-14) §3's review class changes once more. A translation that joins through a **declared**
foreign key onto the hub's own table is fully determined by the catalogue and the decided key, and the generated
tests refuse an unmatched reference at build time; it is a **disclosure**, grouped by its key as WP116 made it. The
decision per key remains for a translation from an **inferred** key (ADR-0018) and for one that projects a homonym
(WP89). The gates `E_LINK_TRANSLATION_UNRATIFIED`/`E_SAT_TRANSLATION_UNRATIFIED` are unchanged: the key licence a
translation stands under is still ratified by a human at the resolution checkpoint. Built as WP128. The ADR's text
stays as drafted.
