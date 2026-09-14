---
type: kickoff
status: not-measured
updated: 2026-09-14
---

# Kick-off WP38 — Translated subtype feeds

The satellite half of WP36. Keyless with a Postgres build; the live chain is the user's call.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-14 (the sales-representative trace, the §6 correction).
2. `wp38-translated-subtype-feeds-spec.md` — §2 twice: the rule fires only on DECLARED evidence.
3. `agents/entity_resolver.py::render_resolution_prompt_section`, `link_proposal.py`
   (`_translation_target`, `resolve_fk_target`, the applier), `agents/staging_generator.py`
   (`collect_staging_specs` satellite branch, `render_translation_model`, `build_staging`),
   `agents/validator.py` (`E_LINK_TRANSLATION_UNRATIFIED`, `E_LINK_KEY_NOT_IN_SOURCE`),
   `demo/fk_links_postgres/build_vault_models.py`.

## Build order
1. Guards first, committed alone (spec §4). 2. `Satellite.key_translation`, the flag kind,
   the schema strip. 3. The applier: ratified same-as + declared FK → no hub, translation on
   the matching satellites. 4. Prompt section: the new sentence, only with evidence. 5. Staging:
   the translation loop over every spec, the satellite stage reading the view. 6. Gates.
   7. Tests per §5; demo extension; `dbt build` on Postgres. 8. Replay over the recorded
   step-5 attempts of the weekend (`eval/replay_collision_remedy.py` as the pattern) — the
   prediction, before anyone pays. 9. Docs: manuals 7 and 9, index, CHANGELOG, log.
