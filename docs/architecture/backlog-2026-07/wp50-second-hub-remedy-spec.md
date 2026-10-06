---
type: spec
status: not-measured
updated: 2026-10-06
---

# WP50 — A remedy with memory against the second hub of one person

Status: **Approved and in progress** (2026-10-06, user: „ok, bau Variante 2, die Remedy gegen den
zweiten Hub") · Owner: Mischa Eismann · Author: Claude. Touches `E_LINK_KEY_WRONG_COLUMN`
(2026-09-15), the repair memory (WP44, WP49), the modeler's `drop_retired`; relies on WP38's
subtype feeds and WP39's two-hop translation for the shape it points the modeler to. No prompt
change; no model call.

## 1 Problem, measured

Fourth chain, `20261005T234048650821Z`, step 5 (`docs/log.md` 2026-10-06): the modeler built
`hub_sales_person` on `SalesPerson` keyed `BusinessEntityID` — a table whose key is `Employee`'s
surrogate, in a vault that already has `hub_employee` — and connected `link_store_sales_person`
to it, hashing the participation from `Store.BusinessEntityID`, the store's own key. The gate
refused (correctly) and told the modeler the alias is not its to invent; the ratified key for
`Store.SalesPersonID` had been resolved to `hub_employee` before modelling and repaired nothing on
the hub the modeler built instead; the proposer had already built `link_store_employee`, the
right relationship. Three attempts, red. This is the two-hubs-on-one-source-entity defect
(`docs/log.md` 2026-09-16, CLAUDE.md) seen from the key side: `hub_sales_person` and
`hub_employee` are one person. The project's stance is one entity, one hub; WP38 built the
subtype feed so a `SalesPerson` satellite hangs on `hub_employee`.

## 2 The rule

**A hub keyed on another hub's surrogate, where the vault has that hub, is the second hub of one
entity; the gate says so and the loop remembers it.**

`rules.second_hub_remedy(hub, model, declared)`: the hub binds a declared table `T`
(`hub_binds_to_source_table`); `T` declares exactly one single-column key on the hub's key
column into another table `U` (`T.key → U.u`, the WP39 onward key); a hub of the model binds `U`.
Then the hub is the second hub of `U`'s hub, and the remedy says: take the participation from
`U`'s hub through the translation `R.k → T → U` (the vault may carry that link already), hang the
satellites read from `T` on `U`'s hub (a subtype feed, WP38), do not build the hub — a re-emitted
copy under any name is dropped. The `E_LINK_KEY_WRONG_COLUMN` issue carries the remedy and
retires the hub (by shape, WP49). `drop_retired` then drops the hub, every link naming it and
every satellite on them — the satellites' payload as `retired_orphan` decisions, as today. Where
the condition does not hold (no onward key, no hub on `U`) the gate keeps today's message and
retires nothing: the second-hub reading is only ever made on declared evidence.

## 3 Guards before the change

1. `second_hub_remedy` names `hub_employee` for `hub_sales_person` on the sales schema; `None`
   when `SalesPerson` declares no onward key or no hub binds `Employee`.
2. On the fourth chain's step-5 shape (fixture cut from the persisted model: `hub_store`,
   `hub_sales_person`, `hub_employee`, `hub_business_entity`, `link_store_sales_person`,
   `link_store_employee`, the three `SalesPerson` satellites), the validator's wrong-column issue
   carries the remedy naming `hub_employee` and `SalesPerson`, and retires `hub_sales_person` by
   shape (`SalesPerson`, `BUSINESSENTITYID`); without `SalesPerson`'s onward key the issue has no
   remedy and nothing is retired.
3. With that retirement, the re-emitted shape loses `hub_sales_person`, `link_store_sales_person`
   and the three satellites (three `retired_orphan` decisions naming their payload); `hub_store`,
   `hub_employee` and `link_store_employee` stay; the validator raises no
   `E_LINK_KEY_WRONG_COLUMN` afterwards.

## 4 Pre-registration

Replayed on the fourth chain's step 5: attempt 1's gate retires `hub_sales_person`; if attempt 2
re-emits it (under any name) it is dropped with `link_store_sales_person` and the three
satellites, and the step is green on this class — the `Store` relationship stands as
`link_store_employee`. If the modeler follows the remedy instead (hangs the satellites on
`hub_employee` as subtype feeds, no second hub), the step is green with the payload kept. On the
next chain: no `E_LINK_KEY_WRONG_COLUMN` of this shape survives; `review_decisions` may rise by
the orphaned satellites (≤ 3) if the memory, not the modeler, resolves it.

## 5 Not in this WP

Re-resolving a ratified proposal's key against the merged model (variant 1, not chosen); carrying
retirements across chain steps; a resolver-side rule that proposes the subtype same-as before
modelling (WP29/WP38 already can, when the resolver sees it).

## 6 Results

*(appended after the change)*
