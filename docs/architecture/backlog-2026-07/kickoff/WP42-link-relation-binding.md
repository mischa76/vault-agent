---
type: kickoff
status: not-measured
updated: 2026-09-16
---

# Kick-off WP42 — A link's relation, resolved by more than its name

The modeler names links; the catalogue names tables. Where the two differ, every key repair and
every link gate is blind today — on 63 % of the links six chains built.

## Read first
1. `CLAUDE.md`; `docs/log.md` 2026-09-16 (the paid chain: `link_bom`, `link_currency_rate_currencies`).
2. `wp42-link-relation-binding-spec.md` — §2 is the whole rule: name, else unique offer, else nothing.
3. `wp41-role-columns-from-declared-keys-spec.md` §2 (the pairing this unblocks), ADR-0013.
4. `rules/dv2_rules.py` (`construct_binds_to_source_table`, `hub_binds_to_source_table`),
   `link_proposal.py` (`resolve_fk_target`, `apply_key_licenses`), `agents/validator.py`
   (`E_LINK_KEY_NOT_IN_SOURCE`, `E_LINK_KEY_WRONG_COLUMN`).

## Build order
1. Guard first, committed with spec and kick-off. 2. `rules.resolve_link_relation` with its two
tiers and a typed reason. 3. The three call sites. 4. Tests per §5. 5. Replay over the six chains,
before/after, every gate code. 6. Demo + `dbt build`. 7. Docs.

## The trap
Tier 2 makes the gates stricter on links that were invisible to them. Expect red steps in the replay
that were green out of blindness, not out of health. That is the finding — record it, do not soften
the rule to make it go away.
