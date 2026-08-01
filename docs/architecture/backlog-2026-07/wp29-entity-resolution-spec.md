# WP29 — Entity resolution against an existing vault (brownfield Phase 2)

Status: Proposed · Size: M · Depends on: WP23 + WP28 merged (both landed) ·
Source: `spike-entity-resolution-results.md` §6 (the spike's D6 recommendation, measured)

## 1. Problem

Brownfield mode extends a vault today only because the *human* answers the one question it
cannot: "the new source calls this PARTNER — is that the existing `hub_customer`, or a new
hub?" The spike measured whether the agent can propose that answer safely and found it can:
zero false merges across 25 runs, 1.000 on every metric clean, and — the decisive property —
honest degradation, answering `unresolved` at low confidence exactly where the evidence runs
out. This WP builds the assist the spike recommends, under the four conditions it set.

## 2. Target design [ENFORCE]

### 2.1 A pre-modeling agent, not a prompt section

New `agents/entity_resolver.py`, running BEFORE `dv2_modeler` on an extension run. The
spike's §3.5 reasoning is binding: once the modeler names a construct, WP23's `merge_models`
folds it by name and the decision is already made, so the proposal must exist — and be
ratifiable — before modelling. Inert unless BOTH `state.existing_model` and
`state.source_schemas` are set (the ADR-0004 grounding-gate pattern): greenfield and
ungrounded runs must be byte-identical, guarded by `test_greenfield_inertness.py`.

One `ForcedToolCaller` pass, Sonnet-tier (measured sufficient; do not reach for the heavy
model without a measurement). Input: the existing construct inventory
(`render_extension_prompt_section` already builds it), the declared schema, the concepts.

### 2.2 The output shape, and same-as as a first-class result

`state.resolutions: ResolutionProposal` promoted from `eval/resolution.py` into `state.py`
(one definition, re-exported for the eval assets — the WP9 precedent). Per concept:
`resolution ∈ {construct name | NEW | same_as_candidate | unresolved}`, `same_as`,
`confidence`, `category`, `evidence: list[str]`, `ratification_status`.

**Same-as ends its deferral** (charter §3.5, spike §3.4): asserted-equivalent-but-differently-
keyed concepts produce TWO hubs plus a flagged candidate. Never a silent merge.

### 2.3 The category is DERIVED, never self-reported

Spike condition 1, from a measured failure: the model reported `semantic` for every case,
including the exact-key ones where its answer was right. So the category is computed from the
evidence in `rules/`: `exact_key` (the concept's key normalises to the existing business key)
> `key_overlap` (a cross-reference asserts it) > `comment_grounded` (the deciding evidence is
a documented comment) > `semantic`. The model's own claim is ignored.

### 2.4 Post-validation keeps the WP9 safety property

A resolution naming a construct that does not exist becomes `unresolved` with the violation
appended to its evidence — never a silent drop, never an invented hub. Same for a `same_as`
target. This is prototyped and works; it must survive into production unchanged.

### 2.5 Ratification

`resolutions.review.yml` beside `mappings.review.yml`, plus
`resume --resolve "concept=hub_name"` for single items. Unresolved and same-as candidates
join the ADR-0006 review queue (`FlagKind.RESOLUTION_UNRESOLVED` /
`RESOLUTION_SAME_AS`, aggregatable). A ratified resolution steers the modeler by NAME — the
existing hub's name enters the extension prompt section as the name to reuse.

`requires_signoff` semantics: unchanged. An unresolved concept is honest output, not a
blocker — the same call WP9 made for mapping gaps.

## 3. Tests (keyless)

1. Inertness FIRST: greenfield, and extension-without-schema → byte-identical, no LLM call.
2. Category derivation: each of the four tiers from its evidence shape; the model's
   self-reported category is ignored (pin it by feeding a wrong one).
3. Post-validation: unknown construct → unresolved + evidence; unknown same-as target → same.
4. Same-as round-trip: candidate → review file → `--resolve` → two hubs, flag pruned.
5. Ratified resolution reaches the modeler prompt as the name to reuse.
6. Review-queue classification and aggregation for both new flag kinds.

## 4. Acceptance criteria

1. **`false_merge_rate` = 1.000 over ≥ 5 live repeats** on `brownfield_resolution`. This is
   the product's promise, not a quality score; anything below is a defect.
2. **Trap 5 (`undecidable`) resolves to `unresolved`.** MEASURED 2026-07-29 (memo §6a):
   `unresolved` 5/5 clean, with evidence naming the missing cross-reference explicitly, and
   the result held when the prompt sentence that described the trap was removed. The WP must
   reproduce it. Note the measured caveat: BLINDED, this concept flips to `NEW` at confidence
   0.88 — no false merge, but a confident wrong answer, because the trap's difficulty lives
   in the comment that blinding removes. Do not lean on the confidence number alone; the
   derived category (§2.3) is what carries the reviewer's attention.
3. `resolution_accuracy` ≥ 0.8 clean; the blinded probe re-run shows accuracy falling while
   `false_merge_rate` holds (honest degradation preserved in production, not just in the
   prototype).
4. Greenfield/ungrounded byte-identity; WP23/WP28 guards untouched.
5. Standard DoD.

## 5. Out of scope

Phase 3 foreign-vault introspection; same-as LINK generation (the candidate is flagged and
ratified here — what the vault does with a ratified same-as is its own decision); any change
to WP23's merge/gate machinery.

## 6. Addendum [2026-08-01] — §2.5 never said WHEN the ratification happens

§2.5 says a ratified resolution steers the modeler by name. It does not say at which point in
the run a human gets to ratify, and the build filled that silence with the only checkpoint
that existed: the ADR-0006 sign-off gate. That gate runs after `source_mapper` — after
modelling, code generation and validation — so a decision made there cannot reach the modeler
it is about, and nothing carried it into a later run. The steering path was therefore
unreachable end-to-end. Recorded in `docs/log.md`, 2026-08-01.

**§2.5 is amended:** ratification happens at its own checkpoint, between `entity_resolver` and
`dv2_modeler`. The pause is conditional — an undecided merge or same-as candidate must be
waiting — so greenfield, ungrounded and NEW/unresolved-only runs are unaffected, and §4's
acceptance criterion 4 (byte-identity) still holds. The decision payload is unchanged:
`resume --resolve` / `--resolutions` / `--accept` mean the same thing at either checkpoint.

What this does NOT settle: whether a ratified decision should also persist beside the model
(`metadata/resolutions.yml`) so a *later* increment is steered without re-asking. That is the
WP33 problem one level up, it is a separate architectural decision, and it is deliberately
left open here rather than assumed.
