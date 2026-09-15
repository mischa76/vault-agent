---
type: kickoff
status: not-measured
updated: 2026-09-15
---

# Kick-off WP41 — Role columns from declared keys

A role names its column; a ratified key says so; greenfield gets the same checkpoint as extensions.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-15 (paid chain, the three candidates, `E_LINK_KEY_WRONG_COLUMN`).
2. `wp41-role-columns-from-declared-keys-spec.md` — §2: licenses in greenfield, pairing per relation
   and hub, role projection, participation-keyed satellite repairs.
3. ADR-0009 (roles), ADR-0013 (translation), `wp40-intra-increment-key-licenses-spec.md` §2.
4. `link_proposal.py` (`collect_link_proposals`, `propose_links`, `apply_key_licenses`),
   `agents/dv2_modeler.py` (applier block, schema strip), `agents/staging_generator.py`
   (`collect_staging_specs`, `render_translation_model`), `agents/validator.py` (role warning,
   satellite gates, `E_LINK_KEY_WRONG_COLUMN`), `rules/dv2_rules.py` (role helpers).

## Build order
1. Guard first, committed with spec and kick-off. 2. `rules`: `role_names_column`,
   `participation_key`. 3. Proposer in greenfield (licenses only). 4. Modeler applies licenses in
   greenfield. 5. Pairing per relation and hub; role participations; satellite aliases and
   participation keys; schema strip. 6. Staging: role projection; satellite aliases. 7. Gates.
8. Tests per §4; flip the guard pins with their reason. 9. Replay steps 1 and 3 before/after.
10. Demo + `dbt build`. 11. Docs.
