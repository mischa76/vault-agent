---
type: spec
status: not-measured
updated: 2026-10-06
---

# WP49 — The repair memory retires a hub by its shape, not only its name

Status: **Approved and in progress** (2026-10-06, user: „ok, bau die Form-Retirierung für Hubs") ·
Owner: Mischa Eismann · Author: Claude. Extends WP44 §2.1 the way WP46 §2.2 extended it for
satellites. No prompt change; no model call.

## 1 Problem, measured

Third chain, `20261005T160357535338Z`, step 5 (`docs/log.md` 2026-10-05): attempt 1 built
`hub_person_sales` on `Customer` keyed `PersonID` beside `hub_customer` on `AccountNumber`; the
collision remedy retired it **by name**; attempt 2 complied; attempt 3 re-emitted the same hub —
same entity, same key — as `hub_person_customer`. Neither the instruction in the payload („the
construct `hub_person_sales` is retired") nor `drop_retired` recognised it: both key a hub by its
name. The gate did, and fired on the last attempt; the step ended red, and the renamed hub was one
of three zero-satellite hubs that failed WP34 §6's invention clause. WP44's own entry had named
the gap as an assumption on 2026-10-04.

A hub's identity is not its name. It is the source entity it is built from and the business key
it is hashed on — which is exactly what `E_HUB_HK_COLLISION` compares.

## 2 The rule

**A retired hub stays retired under any name.** `RetiredConstruct` of kind `hub` carries
`source_entity` and `key_columns` (the normalised `hub_key_columns`, so a composite key compares
as a tuple). The validator records both when it retires a hub. `drop_retired` drops a hub when its
name matches **or** when its normalised source entity and key columns match a retired hub's —
with the links naming it and the satellites parented on them, as today; the flag says the hub was
re-emitted under another name. The payload's `retired_constructs` carry `source_entity` and
`business_key` beside `name`, so the instruction forbids the shape: no hub on `Customer` keyed
`PersonID`, whatever it is called.

The kept hub of the pair is never affected: it has a different key, so its shape never matches.

## 3 Guards before the change

1. A `RetiredConstruct` of kind `hub` recorded by the validator carries the hub's `source_entity`
   and `key_columns`.
2. Replay of step 5 attempt 3 (fixture cut from llm_call 110): with `hub_person_sales` retired as
   shape `(Customer, PERSONID)`, the re-emitted `hub_person_customer` is dropped with the links
   naming it; `hub_customer` stays; one `retired_reemitted` flag naming the rename; the
   validator raises no `E_HUB_HK_COLLISION` afterwards.
3. The retry payload's `retired_constructs` entries carry `source_entity` and `business_key`.
4. A hub with the retired entity but another key passes (shape differs); a retirement without
   shape (an older record) still drops by name.

## 4 Pre-registration

Replayed: step 5 of the third chain ends attempt 3 without the collision; the invention clause
counts 2 zero-satellite hubs (`hub_shopping_cart`, `hub_transaction`) — within WP34 §6's bound —
unless dropping the hub's links fires something else. On the next chain: a renamed duplicate
costs one backstop fire and no red step.

## 5 Not in this WP

Carrying retirements across chain steps (the WP29 persistence decision); the `extension_conflict`
severity; more attempts per step.

## 6 Results

*(appended after the change)*
