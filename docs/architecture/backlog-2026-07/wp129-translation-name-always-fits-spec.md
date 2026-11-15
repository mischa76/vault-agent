---
type: spec
status: not-measured
updated: 2026-11-15
---

# WP129 — A translation model's name fits the platform's identifier limit whenever the stage's own name does (C65)

Status: **Approved and in progress** (2026-11-15, within the owner's instruction to regenerate the shipped demo: a
demo whose project the warehouse refuses is not one) · Owner: Mischa Eismann · Author: Claude. Candidate C65.

## 1 What is wrong

WP102 shortens a translation view's name to `<stage>_via_<n>_<digest>` when the full name exceeds the platform's
limit, and flags what is still too long (`GENERATION_GAP`: „the construct it stages needs a shorter name"). The
short form adds 13 characters to the stage's name, so on PostgreSQL every stage longer than 50 characters that
reads through a translation cannot be named — although the stage itself fits. The twenty-sixth chain (2026-11-14)
produced `stg_business_entity_sales_territory_assignment_details` (54 characters, legal) and its view
`stg_business_entity_sales_territory_assignment_details_via_1_bbad72` (67): dbt-postgres refused the relation, the
satellite and its tests were skipped. WP102 met the case only for a construct whose *own* name is too long; since
WP125 hubs sit on natural keys and a translation is the ordinary case, so the room a name has left is no longer the
construct's affair. Nothing can be done about it at sign-off: the flag asks for a shorter construct name and no
answer at a checkpoint renames a construct.

The view's name is the generator's alone — the stage's `source_model`, the view's file and its `schema.yml` are
written in the same pass and nothing else refers to it. WP102's reason not to truncate („a truncated name is a
different model than every reference to it") holds for a stage, not for this view.

## 2 The rules

1. Unchanged: the full name where it fits; WP102's short form `<stage>_via_<n>_<digest>` where that fits — byte for
   byte, digest included.
2. **Where the short form does not fit either**, the name is `<head>_via_<n>_<digest>`: `<head>` is the stage's name
   cut to the room the suffix leaves (a trailing underscore dropped), and the digest is six hex digits of a SHA-256
   over the stage's **whole** name and the joined list — two stages that share a head, or one stage through two
   different lists, never share a view.
3. The check at render time (WP102 rule 3) is unchanged: a stage whose own name exceeds the limit is still flagged,
   never truncated.

## 3 Not done

No gate on a raw-vault construct's length (WP102 rule 4 left it open; still open). No change to any name that fits
today.

## 4 Pre-registration (keyless)

- **P1** guards (`tests/test_wp129_translation_name_fits.py`) red first — except the pin of WP102's short form,
  green by design before and after — then green.
- **P2** suite, ruff, bare mypy green with no key reachable; no fixture moves.
- **P3** live: the paid chain that regenerates the demo (pre-registered separately) builds on PostgreSQL with no
  relation refused for its length. If no stage over 50 characters reads through a translation there, P3 stays
  unmeasured live and the entry says so.
