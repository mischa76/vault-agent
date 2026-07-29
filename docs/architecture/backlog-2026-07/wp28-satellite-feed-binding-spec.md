# WP28 — Satellite feed binding on multi-source hubs

Status: Proposed · Size: S/M · Depends on: WP24 + WP23 merged (both landed) ·
Source: ADR-0011 (Accepted 2026-07-29, incl. the sharpened acceptance signal)

## 1. Problem

ADR-0011 decided the three-case semantics for a satellite on a multi-source hub; today
the middle case — `source_table` naming one of the hub's feeds — is rejected by
`E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB`, although it is the DV2.0-canonical shape
(one satellite per source system) and the natural output the modeler keeps producing on
the brownfield case (REQ-107, 0/3 steerable). Both currently available behaviours are
wrong for single-feed attributes: the gate rejects the correct form, and the WP10 split
demands the attributes from every feed's staging (measured probe in the ADR). This WP
implements the decision.

## 2. Target design [ENFORCE] — ADR-0011's sketch, made precise

### 2.1 The predicate narrows (one place)

`rules.source_table_on_multi_source_hub()` — the single point validator, code generator
and staging generator ask (WP24 §2.2) — returns True (= still an error) only when the
satellite's `source_table` does NOT name one of the parent hub's feeds. "Names a feed"
= normalised table-name match against `Hub.sources[*].source_table`, INCLUDING the
materialised legacy feed of a grandfathered hub (WP23: a single-source hub gaining feeds
carries its original feed explicitly, so the match needs no special case — assert that
with a test rather than assuming it). Non-effectivity satellites only, as today.

### 2.2 Code generator: bind, don't split

On a multi-source hub, a (standard or multi-active) satellite whose `source_table` names
feed F is rendered ONCE: satellite name unchanged (no per-source suffix — there is only
one), `source_model` = F's staging model via the same naming the hub uses for F
(`multi_source_staging_name`, respecting WP23 grandfathering: F being the legacy feed →
the unsuffixed legacy staging name). The existing GENERATION_GAP flag on this path
disappears for the feed-naming case and stays for the unknown-table case (which the
narrowed gate blocks upstream anyway — defense in depth, WP24 pattern).

### 2.3 Staging generator: the satellite's columns go to ONE spec

`collect_staging_specs`: a feed-bound satellite contributes its attributes, CDK and
hashdiff to **that feed's** staging spec ONLY — not to every per-source spec (this fixes
the ADR's probe: the core staging stops demanding CRM columns), and NOT to a dedicated
orphan `stg_<sat base>` (the WP24 finding-3 shape must not come back). The
finer-grain-relation branch (`source_table` naming a non-feed) remains reachable only
for single-source parents, unchanged.

### 2.4 Validator message + docs

The narrowed gate's message lists the hub's available feeds (ADR consequence: the
distinction between "bound to a feed" and "finer-grain relation" must be legible).
Update in the same commit: `docs/operations/08-validation-gates.md` (narrowed meaning),
WP24 spec §2.2/§5 (a dated note that ADR-0011 resolved the deferred decision — do not
rewrite history), operations §6.7 (the brownfield limitation paragraph), and the
`bank_extension` case file's recorded-limitation note.

### 2.5 Steering rule deleted (WP20/WP16 precedent)

Delete `no_source_table_on_multi_source_hub` from the registry; regenerate the prompt
fixture (assert the pre-WP16 block stays a byte-identical prefix) and move the rule's
steering-ledger row to a "deleted" state with the evidence line (0/3 ineffective, form
now blessed by ADR-0011) — the ledger records lifecycle, it never loses history.
Consider (optional, implementer's judgement): a REPLACEMENT steering line that tells the
modeler the feed-naming form is available and what it means — measure need first, do not
add prompt text speculatively.

### 2.6 Composition matrix moves

Update `tests/test_agents/test_feature_composition.py`: the cells involving
`source_table` × multi-source parent change expected outcome from "flagged, not
generated" to "generated, bound to the named feed" (feed-naming) while the unknown-table
cell keeps the error. The §2.3-invariant (one hash-input set per target column across
all staging specs) must hold on the new cells — it is the guard that catches any
regression of this class.

## 3. Tests (keyless)

1. Predicate: feed-naming (explicit feed, legacy/grandfathered feed) → False;
   unknown table → True; single-source parent unchanged; effectivity excluded.
2. Generator: feed-bound sat rendered once, correct staging binding (suffixed and
   legacy-name cases), no GENERATION_GAP flag; unknown table still gated/flagged, no
   model emitted.
3. Staging: attributes/hashdiff only in the named feed's spec; no orphan stg_<sat base>;
   the other feeds' specs unchanged; §2.3 invariant green over the new cells.
4. Validator: narrowed gate fires only on unknown tables, message names available feeds.
5. Steering: registry row gone, fixture regenerated with prefix assertion, ledger row
   updated (pins in `tests/test_steering.py`).
6. Byte-identity: single-source fixtures, WP10 greenfield split (no `source_table`),
   bank/mapping demo guardrails — all untouched.

## 4. Acceptance criteria (per the ADR's sharpened signal)

1. **Primary:** a live `bank_extension` run (≥ 3 repeats) no longer raises
   `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` for the REQ-107 satellite; the generated
   project contains ONE marketing satellite bound to the CRM staging.
2. Reported alongside, not deciding: `validation_gate` (confounded by
   `E_HUB_HK_COLLISION` on hub_campaign/hub_employee — record the number either way).
3. `existing_construct_preservation` stays 1.000 (the extension promise is untouched).
4. No feature combination emits SQL that cannot build without a flag naming it
   (WP24 acceptance #2 re-asserted over the moved cells).
5. Standard DoD; fixture/ledger changes named in the commit body.

## 5. Out of scope

Semantics for a finer-grain relation UNDER one feed on a multi-source hub (ADR-0011 row
3 — its own decision when it appears in the wild), `canonical_hub_key_column` policy,
same-as links, any mapper change.
