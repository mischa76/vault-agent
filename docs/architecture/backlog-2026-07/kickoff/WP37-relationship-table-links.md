---
type: kickoff
status: keyless-only
updated: 2026-09-12
---

# Kick-off WP37 — Relationship-table links

The second deterministic rule the FK evidence needs. Keyless; the live run is the user's call.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-12 (rerun result, extractor fix, the 8/6/2 split).
2. `wp37-relationship-table-links-spec.md` — §2 twice: resolution happens at two times.
3. `link_proposal.py` (`_target_hub`, `_translation_target`, `apply_ratified_link_proposals`,
   `link_source_overrides`), `agents/orchestrator.py::apply_link_decision`, `cli.py` (both
   renderings of link proposals), `eval/run.py` (`link_proposals` metrics).

## Build order
1. Guard first, committed alone. 2. `RelationshipLinkProposal`, `Participation`,
   `LinkProposals.relationships`, `FlagKind.LINK_RELATIONSHIP_INCOMPLETE`. 3. A shared
   `resolve_fk_target` used at both times. 4. Proposer, applier, decision, key `Table.*`.
   5. CLI lines, eval metrics. 6. Tests per §5. 7. Docs: manual 7 and 8, index, CHANGELOG, log.
   8. Offline replay against today's recorded vault — the prediction, before anyone pays.
