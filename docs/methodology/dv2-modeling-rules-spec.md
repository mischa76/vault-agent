# DV2.0 Modeling Rules — Expansion Spec

> **Purpose:** Concrete blueprint for fleshing out `src/vault_agent/rules/dv2_rules.py` (currently
> a thin skeleton ending in `# TODO: populate further from CDVP 2.1 material`) and the matching
> `validator.py` checks. Closes the gap where DV2.0 depth (Unit of Work, link grain, driving keys,
> satellite splitting) is left to the LLM's latent knowledge rather than encoded and enforced.
>
> **Canon of record:** Dan Linstedt & Michael Olschimke, *Building a Scalable Data Warehouse with
> Data Vault 2.0* (Morgan Kaufmann) — the Scalefree/Linstedt trilogy. This spec encodes **DV2.0
> canon only**. Roelant Vos's revisions (NBK over hash, insert-only over end-dating, ELM over
> Link-Satellites, foreign-key links) are deliberately *out of scope here* and are tracked
> separately in [dsaf-mapping.md](dsaf-mapping.md) as ADR-gated alternatives — never silent defaults.

## Design principle: two tiers

Every rule below is classified as one of:

- **[ENFORCE]** — deterministically checkable from the logical model (or generated metadata).
  Belongs in `dv2_rules.py` as data + a `validator.py` check with an issue code. LLM-independent.
- **[GUIDE]** — requires business-semantic judgment that can't be mechanically verified. Belongs in
  the modeler prompt as guidance, and (where possible) produces a *flag for human review* rather
  than a hard pass/fail.

Keeping the line explicit is the point: it's the difference between "the LLM improvises DV2.0" and
"the system enforces what it can and is honest about what it can't."

## 1. Unit of Work & link grain

**Canon.** A Unit of Work (UoW) is the set of business keys that participate in one atomic business
event/relationship and must be loaded together to preserve the link's grain. A link should represent
exactly one UoW: its `connected_hubs` set *is* the unit of work. Splitting one UoW across multiple
links loses the ability to reconstruct the event; merging independent relationships into one link
inflates the grain.

- **[ENFORCE]** A link connects ≥2 hubs. *(already implemented: `E_LINK_TOO_FEW_HUBS`)*
- **[ENFORCE]** A link references hubs only, never another link. *(already implicit via
  `E_LINK_UNKNOWN_HUB`; make it explicit in the rule text.)*
- **[ENFORCE — new]** No two standard links share an identical `connected_hubs` set *and* `link_type`
  → `W_LINK_REDUNDANT_GRAIN` (warning): likely the same UoW modeled twice, or a grain error.
- **[GUIDE]** Identify the UoW from the requirements: which keys form one atomic business event.
  Do not split a single business event across links; do not combine unrelated relationships.
- **[GUIDE]** Degenerate attributes that belong to the *relationship itself* (e.g. an order line's
  sequence number) may sit on the link; descriptive attributes that change over time go in a
  satellite on the link, not on the link.

*State addition:* none required for the enforce checks; consider an optional `unit_of_work: str`
note on `Link` to capture the modeler's UoW rationale for the ADR trail.

## 2. Driving keys & effectivity satellites

**Canon.** When a relationship changes over time and one side is "fixed" while the other rotates
(an employee has one manager *at a time*; a car has one active driver *at a time*), the **driving
key** is the subset of the link's hub references that stays constant. The effectivity satellite
end-dates relationships **per driving key** — without a declared driving key it cannot correctly
close out superseded relationships.

- **[ENFORCE — new]** An `effectivity` satellite's `parent` must be a **link** (not a hub)
  → `E_EFFSAT_PARENT_NOT_LINK`. *(code generator already checks at generation time; mirror it in the
  validator as an independent gate.)*
- **[ENFORCE — new]** An `effectivity` satellite must carry exactly two date attributes
  (start, end) in order → `E_EFFSAT_DATES`. *(mirror the generator check.)*
- **[ENFORCE — new]** An `effectivity` satellite's parent link must declare a `driving_key`, and
  that driving key must be a non-empty **subset** of the link's `connected_hubs`
  → `E_EFFSAT_NO_DRIVING_KEY` / `E_DRIVING_KEY_NOT_IN_LINK`.
- **[ENFORCE — new, codegen]** The code generator MUST *apply* the declared `driving_key` when
  rendering `automate_dv.eff_sat`: `src_dfk` is the hash key(s) of the hubs named in
  `link.driving_key`, and `src_sfk` is the hash keys of the remaining `connected_hubs`. It must
  **not** default `src_dfk` to "the first connected hub." Declaring and validating the driving key
  while the generator ignores it produces a satellite that end-dates by the wrong key yet passes
  validation — see remediation finding **H-1** in
  [review-2026-06-remediation-spec.md](../architecture/review-2026-06-remediation-spec.md).
- **[GUIDE]** Choose the driving key from business semantics: which side of the relationship is
  "one at a time." If no side is single-valued over time, an effectivity satellite is the wrong
  construct — model it as a standard link + standard satellite instead.

*State addition (required):* add `driving_key: list[str]` to `Link` (subset of `connected_hubs`),
populated when any effectivity satellite hangs off it. This is the single most important new field —
it makes driving-key correctness checkable instead of implicit.

## 3. Satellite splitting

**Canon.** Attributes are grouped into satellites by: (1) rate of change, (2) source system,
(3) data classification / security (e.g. PII), (4) data type. One satellite holds attributes that
belong together on all four axes; you split when they diverge.

- **[ENFORCE — new]** An attribute appears in at most one satellite per parent (no attribute lives
  in two satellites of the same parent) → `E_SAT_ATTR_OVERLAP`.
- **[ENFORCE]** A satellite has a non-empty payload. *(already implemented: `E_SAT_NO_PAYLOAD`;
  effectivity sats are date-driven and exempt — already handled.)*
- **[GUIDE]** Split satellites by rate of change, source, and PII/classification. Record the split
  rationale so the ADR can explain why a concept has N satellites.
- **[GUIDE — flag]** A single satellite with an unusually large attribute count *may* need splitting
  → optional `W_SAT_WIDE` heuristic warning (e.g. > 30 attributes) to prompt human review, not a
  hard fail.

*State addition:* optional `split_rationale: str` on `Satellite` for the ADR trail.

## 4. Business key collision

**Canon.** The same business-key *value* from different sources can denote different real-world
objects. DV2.0 handles this with a Business Key Collision Code (BKCC) / source differentiation so a
hub stays unique on (business key [+ collision code]).

- **[ENFORCE — new, warning]** Two hubs built on the same `business_key` field but different
  `source_entity` → `W_BK_COLLISION_RISK`: flag for the modeler/human to confirm whether a collision
  code or source differentiation is needed.
- **[GUIDE]** When sources disagree on what a key means, introduce a collision code; do not silently
  merge.

## 5. Multi-active satellites

**Canon.** A multi-active satellite allows multiple rows valid at once for one parent at one load
time (e.g. several phone numbers). It needs a child dependent key (intra-key subsequence) in its PK.

- **[ENFORCE — new]** `sat_type == "multi_active"` ⇒ `child_dependent_key` is non-empty
  → `E_MASAT_NO_CDK`. *(code generator already enforces; mirror in validator.)*
- **[GUIDE]** Use a multi-active satellite only when the source genuinely carries multiple concurrent
  values; effective-dated single values are *not* multi-active.

## 6. Non-historized / transactional links

**Canon.** Events/transactions that are immutable once recorded are modeled as non-historized
(transactional) links — insert-only, carrying the event payload, no descriptive satellite needed.

- **[ENFORCE]** `link_type == "transactional"` ⇒ `event_timestamp` is set (and `payload` present)
  → `E_TXNLINK_NO_TIMESTAMP`. *(generator requires it; mirror in validator.)*
- **[GUIDE]** Use a transactional link for record-once events; use a standard link + satellite when
  the relationship's attributes change over time.

## 7. Link variants (guidance only, for completeness)

- **[GUIDE]** *Same-as link* — connects two records of the **same** hub deemed equivalent (master-data
  / single-view). Recognize from dedup/MDM requirements.
- **[GUIDE]** *Hierarchical link* — connects a hub to itself in parent/child roles. Recognize from
  self-referencing hierarchies (org chart, BOM).

These are not yet representable in `state.py` (a link connects *distinct named* hubs). Supporting
them is a **separate modeling-feature decision** (candidate ADR), not part of this rules pass.

## Consolidated: proposed new validator issue codes

| Code | Severity | Trigger |
|---|---|---|
| `W_LINK_REDUNDANT_GRAIN` | warning | two links, identical hub set + type |
| `E_EFFSAT_PARENT_NOT_LINK` | error | effectivity sat parent is not a link |
| `E_EFFSAT_DATES` | error | effectivity sat lacks exactly two ordered date attributes |
| `E_EFFSAT_NO_DRIVING_KEY` | error | parent link of an effectivity sat declares no driving key |
| `E_DRIVING_KEY_NOT_IN_LINK` | error | driving key not a subset of the link's connected hubs |
| `E_SAT_ATTR_OVERLAP` | error | an attribute appears in two satellites of one parent |
| `W_SAT_WIDE` | warning | satellite attribute count over heuristic threshold |
| `W_BK_COLLISION_RISK` | warning | same business-key field across different source entities |
| `E_MASAT_NO_CDK` | error | multi-active sat without a child dependent key |
| `E_TXNLINK_NO_TIMESTAMP` | error | transactional link without event timestamp |

Several of these (`E_EFFSAT_*`, `E_MASAT_NO_CDK`, `E_TXNLINK_NO_TIMESTAMP`) already exist as
**generation-time** checks in `code_generator.py`; mirroring them in the **validator** gives the
independent, defense-in-depth gate the project already values, and lets them fire even on a model
that never reaches generation.

## Consolidated: proposed `state.py` additions

1. `Link.driving_key: list[str]` — **required** for the effectivity/driving-key enforcement. Subset
   of `connected_hubs`.
2. `Link.unit_of_work: str | None` — optional UoW rationale (ADR trail).
3. `Satellite.split_rationale: str | None` — optional satellite-split rationale (ADR trail).

## Suggested rollout order

1. Add `Link.driving_key` to `state.py` + the modeler tool schema and prompt guidance.
2. Expand `dv2_rules.py`: add the structured rule statements (UoW, driving key, splitting,
   collision) and any threshold constants.
3. Mirror the generator-time checks into `validator.py` and add the new enforce checks above.
4. Add unit tests per new issue code (deterministic — no API key).
5. Update [dv2-rules-cheatsheet.md](dv2-rules-cheatsheet.md) so the human-facing cheatsheet and the
   encoded rules stay in sync (it currently has the same `TODO`).

## Explicitly out of scope (tracked in dsaf-mapping.md)

Natural Business Keys vs hash, insert-only vs persisted end-dating, ELM relationship-Hubs vs
Link-Satellites, foreign-key links, Persistent Staging Area, PIT/Bridge generation. These are Vos
revisions or architectural layers — each its own ADR, not part of encoding the DV2.0 canon.
