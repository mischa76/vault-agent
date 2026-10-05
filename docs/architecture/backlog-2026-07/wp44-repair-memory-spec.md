---
type: spec
status: not-measured
updated: 2026-10-04
---

# WP44 — Repair memory: a hub the remedy retired does not come back in a later attempt

Status: **Approved and in progress** (2026-10-04, user: „Ok, leg los" on the analysis of the two
Sales failures) · Owner: Mischa Eismann · Author: Claude. Touches the re-model loop (WP3,
`route_after_validation`), `E_HUB_HK_COLLISION` and `rules.hub_collision_remedy` (2026-09-13),
WP16 (backstop telemetry), WP43 (the role of the new flag kinds). No prompt change, no new model
call.

## 1 Problem, measured

Step 5 (sales) of the chain `20260917T181755061438Z` ended red on `E_HUB_HK_COLLISION`:
`hub_shopping_cart` (key `ShoppingCartID`) beside `hub_shopping_cart_item` (key
`ShoppingCartItemID`), both on `ShoppingCartItem`. The hash key is named after the source entity
(`_hub_hashkey`: `SHOPPINGCARTITEM_HK`) and there is one stage per source entity, so the gate is
right as the generator stands.

The trace (llm_call indices 105, 106, 107 — the step's three modelling attempts) shows the loop
oscillating, not failing to converge:

| attempt | cart hubs emitted | cart links | cart satellites |
|---|---|---|---|
| 1 (105) | both | 2 | `sat_shopping_cart_item_detail` on the item hub |
| 2 (106) | `hub_shopping_cart` only | 0 | 0 |
| 3 (107) | both again | 2 | the same satellite again |

Attempt 1's validator attached the deterministic remedy „drop `hub_shopping_cart_item`; keep
`hub_shopping_cart` — the business-key identifier ranked `ShoppingCartID` 0.78,
`ShoppingCartItemID` 0.72". Attempt 2 **followed it**. Attempt 3 was triggered by other errors
(`E_SAT_KEY_NOT_IN_SOURCE`, a different class) and re-asked for the whole model; the repair lived
only in the previous answer and nowhere the loop could hold it, so the hub returned. The rule
already decides which hub stays. What is missing is a hand that keeps it decided.

## 2 The rule

**A construct the remedy retired stays retired for the rest of the run.**

1. **The validator records the retirement from the typed remedy, never from its text.**
   `ValidationIssue` gains `retires: list[str]`; the collision gate fills it from
   `HubCollisionRemedy.drop`. After the checks, `ValidatorAgent.run` appends every retired name to
   `state.retired_constructs` (typed `RetiredConstruct`: name, kind, the gate code, the attempt),
   once per name. An inherited pair (`drop == []`) retires nothing — nothing this run emits can
   remove it.
2. **The modeler refuses a retired construct's return, deterministically, before the merge.**
   After `_validate_model` and before any applier or `merge_models`, `drop_retired` removes every
   hub whose name is retired, every link that names a retired hub, and every satellite whose
   parent is a retired hub or a link so removed. Each removal is one typed flag:
   `retired_reemitted` for the construct itself (a disclosure under WP43 — the backstop repaired
   it), `retired_orphan` for a dependent that lost its parent (a decision — the payload it
   carried needs a home: on this chain `Quantity`, `DateCreated` of the cart item, whose DV2.0
   place is a link cart–product with `ShoppingCartItemID` as dependent child key; that is a
   modelling act the rule does not take). One `backstop` trace event per fire,
   `backstop_id="retired_reemitted"`, so the WP16 telemetry counts it.
3. **The modeler is told.** The retry payload carries `retired_constructs` (name, kind, code)
   beside `previous_validation_issues` — data in the same channel the remedy already travels in,
   no system-prompt change, no steering-registry line. The deterministic refusal is the
   guarantee; the payload is the shortcut, as the project says of every backstop.

Branching is on `HubCollisionRemedy.drop`, `RetiredConstruct.name`, `FlagKind` — never on
message text (CLAUDE.md invariant). A gate refuses; this backstop repairs and announces itself
(CLAUDE.md, „A gate refuses; a backstop repairs").

## 3 Guards before the change

Committed first, failing; then the change:

1. The validator records `state.retired_constructs` from a collision whose remedy drops a hub;
   an inherited pair records nothing; the issue carries `retires` as a typed list.
2. With `hub_shopping_cart_item` retired, the modeler run over the attempt-3 cart slice
   (`tests/fixtures/wp44/attempt3_cart_slice.json`, cut verbatim from llm_call 107) yields a model
   without that hub, without the two links naming it and without its satellite; one
   `retired_reemitted` flag and three `retired_orphan` flags; the retry payload names the
   retirement; one `backstop` trace event with `backstop_id="retired_reemitted"`.
3. Validated afterwards, that model raises no `E_HUB_HK_COLLISION`.
4. A run with nothing retired is byte-identical in model and flags (the backstop is inert).
5. WP43's role table classifies both new kinds (its existing guard enforces this).

## 4 Pre-registration — what the replay says

Applying §2 to the saved attempts of step 5: attempt 1 retires `hub_shopping_cart_item`;
attempt 2 is unchanged (it complied); attempt 3 loses 1 hub, 2 links, 1 satellite. Predicted for
the next live chain, **if** the modeler behaves as on 2026-09-17:

- **P1.** `E_HUB_HK_COLLISION` is 0 in every step. Step 5 stays red on the *other* class,
  `E_SAT_KEY_NOT_IN_SOURCE` ×3 behind composite keys — the subject of the next WP, not this one.
- **P2.** Flags: `retired_reemitted` 1 and `retired_orphan` 3 on the chain, all in step 5; the
  backstop fires once. `hub_shopping_cart` remains a zero-satellite hub, as it already was
  (WP34 §6's invention clause does not move).
- **P3.** Nothing else moves: the retirement touches only names the remedy named.
- **P4.** If the modeler never re-emits (as on 2026-09-13, step 5 attempt 2 „dropped as told"
  and no third attempt), the backstop fires zero times and P1 holds by the modeler alone — a
  non-fire is not a failure of this WP; it is the gate behind it doing the work.

## 5 Not in this WP, and what it costs

- **Re-parenting the orphaned payload** (the cart item's `Quantity`, `DateCreated`) onto a link
  with a dependent child key. A modelling act; it is surfaced as a decision item instead. If it
  recurs, a deterministic rule „a dependent of a retired hub whose key references another hub
  moves to the link between the kept hub and that hub, keyed on the retired key" is small — but
  it needs a second case before it is a rule and not a fit to one.
- **The composite-key gap** behind the remaining three errors: WP45.
- **Retiring links or satellites** named by other remedies: no gate other than the collision
  carries a typed `drop` today; the state field and the filter are general, the recording is not.

## 6 Results

*(appended after the change and after the next live chain)*

**2026-10-04 — built, keyless.** Commits `d553739` (guards, failing) and the change commit that
follows it. `ValidationIssue.retires`, `RetiredConstruct`, `state.retired_constructs`,
`drop_retired` in the modeler, the two flag kinds classified in WP43's table, backstop
`retired_reemitted`. Guards 1–5 pass; ruff, mypy, pytest 1078 passed. Replayed on the fixture cut
from attempt 3: 1 hub, 2 links, 1 satellite dropped, no collision afterwards. §4 is **not yet
measured live**.

**2026-10-04 — measured live** (chain `20261004T013339024833Z`, `docs/log.md` „Paid chain run",
2026-10-04). **P1 held:** `E_HUB_HK_COLLISION` 0 in every step. **P2 held by the escape clause
(P4):** the backstop fired zero times — the modeler built one cart hub and the item as a link to
`hub_product`, so nothing was retired. **P3 held.** The mechanism's evidence remains the replay
of §3; this run shows the gate and the modeler agreeing without it.

**2026-10-05 — second live chain** (`20261004T140130528908Z`): the collision class appeared in
step 2 and step 4 attempt 1 (`hub_employee_business_entity`, `hub_vendor_business_entity`), the
remedies were followed in attempt 2, the retirements were sent, the backstop fired 0 times. P4
again: the gate and the modeler agreeing, the memory in reserve.

**2026-10-05 — third live chain** (`20261005T160357535338Z`): the gap named under „Nur angenommen"
on 2026-10-04 was observed. Step 5 attempt 1 built `hub_person_sales` (Customer, PersonID), the
remedy retired it by name, attempt 2 complied, attempt 3 re-emitted the same hub as
`hub_person_customer` — same entity, same key, new name — and the name-keyed memory let it
through; the gate fired again on the last attempt and the step ended red. **The memory must key a
hub by its shape (source entity, business key) beside its name**, as WP46 keys a satellite by
parent and relation. Proposed as the next change; replayable from llm_call 110's payload.
