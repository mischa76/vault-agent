---
type: kickoff
status: not-measured
updated: 2026-09-15
---

# Kick-off WP39 — Two-hop translation

One more hop in the WP36 rule, only where no nearer hub exists. Keyless with a Postgres build.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-15 (the paid chain, the widened gate, the nine refusals).
2. `wp39-two-hop-translation-spec.md` — §2: the nearest hub always wins; one hop, no recursion.
3. `link_proposal.py` (`_target_hub`, `_translation_target`, `resolve_fk_target`, `propose_links`),
   `subtype_feed.py`, `agents/validator.py` (the two satellite gates), the WP38 guard.

## Build order
1. Guard first, committed with spec and kick-off. 2. The hop inside `_translation_target`.
3. Proposer evidence naming the middle table. 4. Subtype feeds: covered referencing tables,
   the prompt sentence, validator lookups by (hub, table). 5. Tests per §5, WP38 pin flipped.
6. Replay the sales step of `20260914T213855724138Z` before and after. 7. Demo + `dbt build`.
8. Docs: manuals 7 and 9, index, CHANGELOG, log, spec addendum with the pre-registration.
