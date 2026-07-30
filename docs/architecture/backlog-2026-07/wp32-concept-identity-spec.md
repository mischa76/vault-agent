# WP32 — Concept identity is (label, entity), not the label alone

Status: **Approved** (2026-07-30, Mischa) · Owner: Mischa Eismann · Date: 2026-07-30
Origin: WP30 §7.3 Finding 1 — found by the independent AdventureWorks instrument, reproduced
keylessly in five lines. No ADR: this is a defect, not a choice between defensible designs.

## 1. Problem

The source mapper identifies a business concept by its **label alone**. Two hubs whose business
keys carry the same label are therefore the same concept to it. That is wrong twice over, and the
second one produces wrong **data**:

```
hubs: hub_phone_number_type (PhoneNumberType), hub_address_type (AddressType),
      hub_contact_type (ContactType) — all keyed "Name"

SourceMapperAgent._concepts  -> [('Name', 'PhoneNumberType')]        # asked ONCE
source_overrides             -> {'PHONE_NUMBER_TYPE': 'PhoneNumberType',
                                 'ADDRESS_TYPE':      'PhoneNumberType',   # <-- wrong relation
                                 'CONTACT_TYPE':      'PhoneNumberType'}   # <-- wrong relation
```

`_concepts` de-duplicates the work-list on `normalize_identifier(concept)`, so two of the three
hubs are never asked about. `source_overrides` then looks the answer up by the same label, so the
one proposal's table is applied to **every** hub carrying it: `stg_address_type` reads
`PhoneNumberType` and hashes `ADDRESS_TYPE_HK` from the wrong relation's rows. It is silent — no
flag, and the `SOURCE_BINDING` flag that would have said "inferred" is *cleared* by the re-bind.

This is the WP24 defect class (wrong data, not a wrong message) and the shape is not exotic:
reference tables keyed on `Name` / `Code` / `Description` are ordinary, and AdventureWorks
`Person` alone supplies three. Measured cost (WP30 §7.3): on `production` **7 of 9** golden pairs
and on `sales` **2 of 5** are missed for this reason alone, each run making exactly one proposal
for a concept labelled `Name`.

The entity is available at every site — `_Concept.entity`, `Hub.source_entity`,
`Proposal.entity` — and is already sent to the model in the payload. Only the *identity* ignores
it.

## 2. Target design [ENFORCE]

### 2.1 One definition of a concept key

`state.concept_key(concept, entity) -> str` — `"<entity>::<label>"` when an entity is known, the
bare label otherwise. In `state.py` beside `Proposal`/`ProposedMapping` because it is an identity
convention of the mapping model, not a Data Vault rule (so not `rules/`). Every site imports it;
none re-derives it. `::` is chosen over `.` so a key never collides with the `TABLE.COLUMN`
syntax the ratification file and `--map` already use.

### 2.2 The key is sent, not inferred

`_Concept` gains `key`; the payload sends it per concept; the prompt's closing line changes from
"keyed by the exact concept label given to you" to keying by that `key` verbatim. Sending the key
rather than asking the model to compose one means a label containing punctuation can never
produce an unparseable key — there is nothing to parse.

### 2.3 Lookup: exact key, then an *unambiguous* label fallback

Two refinements the implementation forced, both from tests that caught the rule being too
permissive — recorded because each is a rule, not a detail:

- **A qualified reference never label-matches a candidate carrying a different entity.**
  `AddressType::Name` must not resolve to `ContactType`'s `Name` merely because it is the only
  proposal so far. The fallback applies when one side carries no entity, not when the two
  disagree.
- **"Ambiguous" and "unknown" are different answers.** `match_concept_refs` returns every
  candidate index, so a caller can refuse when several match (ambiguous) while still allowing a
  human to add a concept nothing matches (unknown). Collapsing both into "not found" would
  either drop a legitimate addition or pick arbitrarily among siblings — and picking arbitrarily
  is the defect. Ambiguity is judged over the run's WHOLE concept universe (proposals plus
  unresolved plus gaps), not just the proposals: a label unique among proposals can still name
  any of three unresolved concepts.

`_post_validate` resolves each concept's decision by normalised key. If the model answered with a
bare label anyway, that answer is accepted **only when exactly one concept in the work-list
carries that label**; when the label is ambiguous there is no fallback and the concept becomes
`unresolved` (flagged for a human).

That asymmetry is the point: a fallback that resolved an ambiguous label would reinstate exactly
this defect, and `unresolved` is the honest answer — this project defers rather than guesses
(the mapper's own `unresolved`, WP7's source-binding flag, the modeler's dropped records). The
unambiguous case keeps today's robustness, which is every case the shipped cases exercise.

### 2.4 Every consumer matches on the pair

- `source_overrides`: hub → proposal on `(business_key, source_entity)`, not the label.
- `merge_decisions`: unchanged in shape — it merges the model's own keys, which are now qualified.
- HITL ratification is **in scope**, because leaving it out would create a new inconsistency
  rather than a smaller fix: with §2.1 in place `mappings.review.yml` can list several proposals
  labelled `Name`, so a label-keyed override file would be ambiguous by construction.
  `mappings.review.yml` emits a `key` per entry; `--map` accepts either form;
  `apply_mapping_overrides` and `apply_hub_sources` resolve with the same
  exact-then-unambiguous-fallback rule as §2.3. A single-source vault's file and commands stay
  byte-identical, since a unique label's key resolves the same way.

### 2.5 Out of scope, deliberately

- **`eval/`**: the concept-mode scorers match golden concepts by label. The AdventureWorks cases
  are column mode (pair-based) and unaffected; `bank`/`messy_insurance` have unique labels, so
  their scores must not move — that is a *regression guard* here, not work.

  **Amended during implementation (2026-07-30), because the original claim was wrong.** Making
  `gaps`/`unresolved` hold keys (§2.4) does force exactly one eval line: `gap_detection`
  compares `state.mappings.gaps` against golden gap *labels*, so it now compares on the label
  half via `split_concept_key`. Recorded rather than quietly done — "no eval change" was stated
  in this spec and did not survive contact with the change. The alternative (keeping the lists
  as labels) was rejected on its own merits: three identical `"Name"` entries tell a human
  nothing and cannot be pruned individually.
- WP30 Finding 3 (`mapping_coverage` conflating mapper quality with modeler key choice). Named
  and left alone, per WP30 §7.3.
- The modeler's *choice* of business-key label. Naming three hub keys `Name` is legitimate; the
  mapper must cope with it.

## 3. Tests (keyless)

1. The reproduction from §1: three hubs keyed `Name` → **three** concepts asked, and
   `source_overrides` binds each hub to **its own** relation. Fails on the pre-WP32 code.
2. `concept_key` round-trip: with and without an entity; a label containing `.` and `::`.
3. Exact-key lookup: qualified keys resolve to the right proposal, per entity.
4. Unambiguous-label fallback resolves.
5. **Ambiguous-label fallback does NOT resolve** — both concepts land in `unresolved` with their
   flags, and neither is bound. The anti-regression pin for this whole WP.
6. `source_overrides` with two same-labelled hubs whose proposals name different tables → two
   distinct bindings (the staging invariant WP24 established: one target column, one input set).
7. HITL: `mappings.review.yml` carries a `key`; `--map` accepts qualified and bare forms; an
   ambiguous bare form is an attributable error rather than a silent pick.
8. `apply_hub_sources` resolves a qualified key.
9. Byte-identity: a single-source model's proposals, review file and overrides are unchanged
   (the ungrounded/unique-label path).
10. The shipped `bank`/`messy_insurance` mapping-scorer tests pass untouched (§2.5).

## 4. Acceptance criteria

1. §3 green; ruff + mypy strict clean; the WP24 composition matrix, staging baseline and both
   demo guardrails untouched.
2. The §1 reproduction, run as a test, binds three hubs to three relations.
3. **Live, against the prediction WP30 §7.3 recorded *before* this fix:** `adventureworks_production`
   `mapping_coverage` 0.222 → ~0.78 and `adventureworks_sales` 0.600 → ~1.000, with no change to
   the mapper's reasoning. A materially different result means the residual is modeler key choice
   (Finding 3) and is recorded as such — the prediction is not adjusted afterwards.
4. `false_friend_hits` stays 1.0 on both: more concepts asked must not mean a `rowguid` bound.

## 5. Budget

Two live runs at 1 repeat ≈ **$6**. WP30 has spent $19.66 of its $40–60 ceiling.
