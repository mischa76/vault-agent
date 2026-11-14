---
type: spec
status: not-measured
updated: 2026-11-14
---

# WP128 — A translation over a declared key is a disclosure; the decision per key remains for an inferred key and a homonym (ADR-0013's note of 2026-11-14, ADR-0021)

Status: **Approved and in progress** (2026-11-14, on the owner's go on the proposal as presented) · Owner: Mischa
Eismann · Author: Claude. Candidate C63.

## 1 What is wrong

WP116 made a translation one decision per key: „confirm the translation model once". With hubs on natural keys
(WP125) the translation is the ordinary case again — the drafted arm of 2026-10-30 carried 51 translated
participations, and the C1 finding counted 55 decisions more than the surrogate-keyed arm, every one of them a
confirmation of a join the catalogue had declared and a human had licensed at the resolution checkpoint. A reviewer
who answers that many confirmations accepts defaults; the decision that deserves attention — a join nobody declared,
a column that only looks like the key — sits among them.

## 2 The rules

1. `PipelineFlag.confirm` (a typed boolean, default false): the flag discloses something a human must still
   confirm. Set on a `link_translation` or `sat_translation` flag when the translation stands on a key **inferred
   from data** (`provenance == "inferred"`, ADR-0018) or when the relation carries a column of the hub key's name
   that the translation does not read (a **homonym**, WP89). Never derived from the message.
2. The review queue synthesises the decision per translated key (WP116) **only for a key with at least one such
   flag**. A key whose every translation stands on a declared foreign key has no decision; its flags stay
   disclosures, grouped by the key as before.
3. A translation flag without a key stays a decision (WP116's rule, unchanged). The gates
   `E_LINK_TRANSLATION_UNRATIFIED` / `E_SAT_TRANSLATION_UNRATIFIED` are unchanged: the licence or proposal a
   translation stands under is ratified at the resolution checkpoint.
4. A state without such a flag serialises as before: the field is omitted where it is false.

## 3 Not done

No change to what is ratified at the resolution checkpoint (a key licence is still pending until answered, an
inferred one still declined by the bulk answer). No change to the generated translation model or its tests.

## 4 Pre-registration

- **P1** guards (`tests/test_wp128_translation_disclosure.py`) red first, then green.
- **P2** suite, ruff, bare mypy green with no key reachable. Changed deliberately: WP116's guards that pin one
  decision per key for a declared translation; the catalogue's two flag meanings; the manual. No artefact baseline.
- **P3** the review-record generations (`eval/wp34_check.py`): the count of a stored chain is not recomputed — a
  chain under ADR-0021 starts a new generation (the paid chain's pre-registration says so).
