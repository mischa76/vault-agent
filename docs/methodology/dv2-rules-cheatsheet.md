# Data Vault 2.0 / 2.1 – Rules Cheatsheet

> Living document. The human-facing mirror of the rules encoded in
> `src/vault_agent/rules/dv2_rules.py` and enforced in `src/vault_agent/agents/validator.py`.
> Canon of record: Dan Linstedt & Michael Olschimke, *Building a Scalable Data Warehouse
> with Data Vault 2.0*. Roelant Vos's revisions are deliberately out of scope here — they
> are ADR-gated alternatives tracked in [dsaf-mapping.md](dsaf-mapping.md), never silent
> defaults. The blueprint behind this encoding is [dv2-modeling-rules-spec.md](dv2-modeling-rules-spec.md).

Each rule is one of two tiers:

- **[ENFORCE]** — deterministically checkable; the validator fails or warns with an issue code.
- **[GUIDE]** — business-semantic judgment; lives in the modeler prompt as guidance.

## Hubs
- One row per unique business key — one hub is one concept with one natural key. **[GUIDE]**
- Columns: HashKey, BusinessKey, LoadDateTime, RecordSource. Hubs hold *only* the business
  key plus DV technical columns — never descriptive attributes.
- A hub must have a non-empty business key → `E_HUB_NO_BK`. **[ENFORCE]**
- A hub with no satellite captures no descriptive data → `W_HUB_NO_SAT` (warning). **[ENFORCE]**

## Links
- Represent relationships between hubs (n:m, transactions, hierarchies). Columns: HashKey,
  HashKey(of each related hub), LoadDateTime, RecordSource. Links hold *only* hub references
  — no descriptive attributes, no business keys.
- A link connects ≥2 hubs → `E_LINK_TOO_FEW_HUBS`; it references known hubs only, never
  another link → `E_LINK_UNKNOWN_HUB`. **[ENFORCE]**
- **Unit of Work (UoW):** a link represents exactly one atomic business event; its
  `connected_hubs` set *is* the UoW. Don't split one event across links or merge unrelated
  relationships into one. **[GUIDE]** — record the rationale in `unit_of_work` for the ADR.
- Two links over the same hub set + `link_type` likely model one UoW twice →
  `W_LINK_REDUNDANT_GRAIN` (warning). **[ENFORCE]**
- Degenerate attributes of the relationship itself (e.g. an order-line sequence) may sit on
  the link; attributes that change over time go in a satellite on the link. **[GUIDE]**

### Link variants
- **Standard** (`link_type="standard"`) — historised relationship.
- **Transactional / non-historized** (`link_type="transactional"`) — record-once,
  insert-only events carrying their payload. Needs an `event_timestamp` → otherwise
  `E_TXNLINK_NO_TIMESTAMP`. **[ENFORCE]**
- **Driving key** — when one side of a relationship is "one at a time" (one manager per
  employee), declare `driving_key` as the fixed subset of `connected_hubs`. Required for an
  effectivity satellite; must be a non-empty subset → `E_DRIVING_KEY_NOT_IN_LINK`. **[ENFORCE]**
- *Same-as* and *hierarchical* links are recognised by the modeler but not yet representable
  in the logical model — a separate modeling-feature decision (candidate ADR). **[GUIDE]**

## Satellites
- Carry descriptive data that changes over time. Columns: HashKey(parent), LoadDateTime,
  RecordSource, HashDiff, business attributes. Each satellite hangs off exactly one parent.
- Parent must be a known hub or link → `E_SAT_UNKNOWN_PARENT`; payload must be non-empty →
  `E_SAT_NO_PAYLOAD`. An attribute lives in at most one satellite per parent →
  `E_SAT_ATTR_OVERLAP`. **[ENFORCE]**
- **Splitting axes** — group attributes that belong together on *all* of: rate of change,
  source system, data classification (e.g. PII), data type; split where they diverge.
  **[GUIDE]** — record the rationale in `split_rationale` for the ADR.
- A satellite wider than **30 attributes** is flagged for possible splitting →
  `W_SAT_WIDE` (warning, heuristic — never a hard fail). **[ENFORCE]**

### Satellite variants
- **Standard** (`sat_type="standard"`) — ordinary descriptive satellite.
- **Multi-active** (`sat_type="multi_active"`) — several rows valid at once for one parent
  (e.g. multiple phone numbers); needs a `child_dependent_key` → otherwise `E_MASAT_NO_CDK`.
  Not the same as effective-dated single values. **[ENFORCE]**
- **Effectivity** (`sat_type="effectivity"`) — tracks a relationship's active period. Parent
  must be a **link** → `E_EFFSAT_PARENT_NOT_LINK`; carries exactly two ordered date
  attributes (start, end) → `E_EFFSAT_DATES`; the parent link must declare a driving key →
  `E_EFFSAT_NO_DRIVING_KEY`. **[ENFORCE]**

## Business keys – heuristics
- Stable over time (the natural identifier doesn't change). **[GUIDE]**
- Unique within the business object's universe (isolates exactly one instance). **[GUIDE]**
- Recognized and used by the business (preferred over a surrogate). **[GUIDE]**
- Not nullable — every instance carries a value. **[GUIDE]**
- **Collision:** the same business-key *value* from different sources can denote different
  objects — introduce a collision code rather than silently merging. The same business-key
  field across different source entities → `W_BK_COLLISION_RISK` (warning). **[ENFORCE]**

## Validator issue codes

| Code | Severity | Trigger |
|---|---|---|
| `E_NO_HUBS` | error | model has no hubs |
| `E_DUP_NAME` | error | a construct name is not unique |
| `E_HUB_NO_BK` | error | hub has no business key |
| `W_HUB_NO_SAT` | warning | hub has no satellite |
| `E_LINK_TOO_FEW_HUBS` | error | link connects fewer than two hubs |
| `E_LINK_UNKNOWN_HUB` | error | link references an unknown hub |
| `E_DRIVING_KEY_NOT_IN_LINK` | error | driving key not a subset of connected hubs |
| `E_TXNLINK_NO_TIMESTAMP` | error | transactional link without event timestamp |
| `W_LINK_REDUNDANT_GRAIN` | warning | two links, identical hub set + type |
| `E_SAT_UNKNOWN_PARENT` | error | satellite parent is not a known hub or link |
| `E_SAT_NO_PAYLOAD` | error | satellite has an empty payload |
| `E_SAT_ATTR_OVERLAP` | error | an attribute appears in two satellites of one parent |
| `W_SAT_WIDE` | warning | satellite attribute count over the heuristic threshold (30) |
| `E_MASAT_NO_CDK` | error | multi-active satellite without a child dependent key |
| `E_EFFSAT_PARENT_NOT_LINK` | error | effectivity satellite parent is a hub, not a link |
| `E_EFFSAT_DATES` | error | effectivity satellite lacks exactly two ordered date attributes |
| `E_EFFSAT_NO_DRIVING_KEY` | error | parent link of an effectivity satellite declares no driving key |
| `W_BK_COLLISION_RISK` | warning | same business-key field across different source entities |
| `E_MISSING_COLUMN` | error | a generated construct is missing a DV-required column |

## Out of scope here (see [dsaf-mapping.md](dsaf-mapping.md))

Natural Business Keys vs hash, insert-only vs persisted end-dating, ELM relationship-hubs
vs Link-Satellites, foreign-key links, Persistent Staging Area, PIT/Bridge generation —
each its own ADR, not part of encoding the DV2.0 canon.
