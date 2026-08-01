# `brownfield_resolution` — what each table is there to test

Moved out of `source_schema.yml` on 2026-08-01 (WP29.1 kick-off item 1). They were YAML
comments, so the pipeline never read them — `yaml.safe_load` discards comments, measured and
pinned by `tests/test_resolution_dataset.py`. But a **blinded requirements author reads the raw
file**, and these sentences state the answers outright; the first attempt at blinded authoring
tripped over exactly that and reported it (`docs/log.md`, 2026-08-01).

Nothing here is new. `golden_resolution.yml` carries the same reasoning in its `rationale`
fields, at greater length and in the machine-readable place. This file exists so that moving the
comments out of the schema loses no prose a human might want, and so the schema can be handed to
an author without handing them the answer key.

**Do not give this file to anyone authoring requirements for this case.**

## The design

The landscape is a DACH contract-management system ("VICTOR"-flavoured, as in
`messy_insurance`) plus its CRM module, anonymised throughout (ATLAS convention). It is
deliberately built so that **name similarity and the correct answer disagree**: the two tables
sharing the "PARTNER" stem resolve in opposite directions, and the table whose name is furthest
from "customer" is the one that IS the customer.

Column comments are the kind a real legacy data dictionary carries — terse, occasionally more
useful than the column names. Those stayed in the schema: they are evidence a real analyst would
have, and removing them would make the case easier than reality, not fairer.

## Per table

| table | role | correct answer |
|---|---|---|
| `vic_partner` | **TRAP 1** — synonym hub | the existing `hub_customer` |
| `vic_kontakt` | **TRAP 2** — false friend | `NEW` |
| `vic_vertragspartner` | **TRAP 3** — similar name, new hub | `NEW` |
| `crm_kunde` (+ `crm_xref_partner`) | **TRAP 4** — same-as | `same_as_candidate` → `hub_customer` |
| `vic_konto` | CONTROL — easy synonym | the existing `hub_account` |
| `vic_vertrag` | CONTROL — plain new entity | `NEW` |
| `vic_migration_altbestand` | **TRAP 5** — undecidable | `unresolved` |

**TRAP 1** is the existing `hub_customer`: same national customer ID, same values. The name
shares nothing with "customer".

**TRAP 2** smells like a customer — name, address, a person — and is not: a contact PERSON at a
corporate customer, with its own key and its own lifecycle. Merging it would push contact IDs
into the customer hub.

**TRAP 3** is a legitimate new hub despite the shared stem with TRAP 1. The counterparty of a
contract is a different concept on a different key; "PARTNER" in the name is the decoy. Taken
with TRAP 1 it is the discriminating pair — a mechanism cannot pass both by leaning on the name.

**TRAP 4** is asserted equivalent to the customer but on a DIFFERENT key. Correct output is two
hubs plus a flagged candidate, never a silent merge.

**TRAP 5** was added after the first spike run, which the memo criticised (§4) for never
offering the hardest case. A legacy migration table whose key values overlap the national
customer ID range — same format, same look, genuinely different population — with no
cross-reference to disambiguate. Nothing in the schema settles it, so the only correct answer is
`unresolved`: a mechanism that decides here is guessing, and one that MERGES here corrupts the
customer hub.
