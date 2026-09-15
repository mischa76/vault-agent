---
type: kickoff
status: not-measured
updated: 2026-09-15
---

# Kick-off WP40 — Key licenses

A ratified foreign key repairs the staging of constructs the modeler built; it never builds one.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-15 (widened gate, WP39, the nine refusals classified).
2. `wp40-intra-increment-key-licenses-spec.md` — §2: license, resolve every attempt, repair only.
3. `link_proposal.py` (`propose_links`, `resolve_fk_target`, `apply_ratified_link_proposals`),
   `subtype_feed.py`, `agents/staging_generator.py` (`collect_staging_specs`, link-parent satellite
   branch), `agents/validator.py` (translation gates, `E_SAT_KEY_NOT_IN_SOURCE`),
   `agents/orchestrator.py::apply_link_decision`, `cli.py` link rendering, `eval/run.py` metrics.

## Build order
1. Guard first, committed with spec and kick-off. 2. `KeyLicense` in `LinkProposals.licenses`,
   `Satellite.participation_translations`, schema strip. 3. Proposer: licenses instead of skips.
4. Decision, checkpoint rendering, metrics. 5. Repair applier after the link applier, every attempt.
6. Staging for link-parent satellites. 7. Gates. 8. Tests per §4. 9. Replay before/after. 10. Demo +
   `dbt build`. 11. Docs.
