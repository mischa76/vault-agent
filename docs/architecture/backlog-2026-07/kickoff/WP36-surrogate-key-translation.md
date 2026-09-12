---
type: kickoff
status: keyless-only
updated: 2026-09-12
---

# Kick-off WP36 — Surrogate→natural-key translation

You are closing the one capability gap the 2026-08-12 audit left: four declared foreign keys
reference a surrogate while the hub is keyed on the natural key. Keyless until §6's live step.

## Read first
1. `CLAUDE.md` — helpers in `rules/`, guard before change, typed fields, graph order.
2. `docs/architecture/adrs/ADR-0013-surrogate-to-natural-key-translation.md` (accepted 2026-09-12).
3. `docs/log.md` 2026-08-12, "The remaining 22 audited" and "The missing links were a separator".
4. `wp36-surrogate-key-translation-spec.md` — binding. §2 (trigger) and §3 (two models) first.
5. Code: `link_proposal.py` (`_target_hub`, `apply_ratified_link_proposals`,
   `link_source_overrides`), `agents/staging_generator.py` (link specs, `bind_sources`,
   `render_stage_model`), `agents/validator.py` (`E_LINK_KEY_NOT_IN_SOURCE`),
   `eval/wp34_check.py` (`unsound_aliases`), `cli.py` (checkpoint rendering of link proposals).

## Build order
1. Guard first: `tests/test_wp36_translation_guard.py` on today's behaviour, committed alone.
2. Types: `KeyTranslation`, the new category, the new skip reason, `FlagKind.LINK_TRANSLATION`.
3. Proposer trigger, applier, flag. 4. Staging: translation model + stage on it + `schema.yml`
   tests + metadata. 5. Gate branch, checker clause, checkpoint text. 6. Docs: manual 7, 8, 9;
   index; CHANGELOG; log. 7. Then, and only then, the protocol's step 1 (free audit) and step 2
   (paid rerun, cap $20).

## Done when
Spec §6 items 1–4 keyless; every existing fixture untouched; the log names what is keyless and
what the rerun measured.
