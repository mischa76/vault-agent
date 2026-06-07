# Data Vault 2.0 / 2.1 – Rules Cheatsheet

> Living document. Source of truth for what the DV2.0 Modeler Agent must enforce.

## Hubs
- One row per unique business key
- Columns: HashKey, BusinessKey, LoadDateTime, RecordSource

## Links
- Represent relationships between hubs (n:m, transactions, etc.)
- Columns: HashKey, HashKey(of related hubs), LoadDateTime, RecordSource

## Satellites
- Carry descriptive data, change over time
- Columns: HashKey(parent), LoadDateTime, RecordSource, HashDiff, business attributes
- Variants: Standard, Multi-Active, Effectivity, Status Tracking

## Business keys – heuristics
- Stable over time (the natural identifier doesn't change)
- Globally unique within the business object's universe
- Recognized by the business (preferred over surrogate)
- Not nullable

(TODO: flesh out with examples and DV2.1 specifics from CDVP 2.1 material)
