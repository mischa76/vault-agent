---
type: spec
status: not-measured
updated: 2026-10-07
---

# WP54 — A gate for the lost payload: a hub whose table no satellite reads

Status: **Approved and in progress** (2026-10-07, user: „bau das Gate für die verlorene Payload“)
· Owner: Mischa Eismann · Author: Claude. Touches the validator and `rules/`; no prompt change,
no model call. A gate, not a backstop: it refuses and feeds the re-model loop with a remedy.

## 1 Problem, measured

Eighth chain, `20261007T041647752430Z` (`docs/log.md` 2026-10-07): WP34 §6 failed on the invention
clause with four zero-satellite hubs. Two carry their payload on link satellites; two carry it
nowhere — no satellite in the model reads `TransactionHistory` (Quantity, ActualCost,
TransactionDate, …) or `PurchaseOrderDetail` (OrderQty, UnitPrice, ReceivedQty, …). Both steps
modelled in one attempt: `W_HUB_NO_SAT` is a warning, a disclosure in the queue, and the modeler
never saw a refusal. The pipeline's output is a vault that silently drops a table's descriptive
columns — the one defect class a reviewer cannot see from the model alone, because what is
missing has no construct.

## 2 The rule

**A hub bound to a declared table of this increment whose payload columns no satellite reads is
refused, with the columns named.**

1. `rules.unread_payload(hub, table, model) -> list[str]`: the table's columns minus the hub's
   key columns (`hub_key_columns`), minus every column of a declared foreign key of the table,
   minus every column some satellite of the model reads from that table — a satellite reads a
   table when `satellite_payload_relations` of it and its parent contains the table (declared
   `source_table`, a hub's `source_entity` or feed), regardless of the satellite's parent (a link
   satellite counts). Compared through `normalize_identifier`.
2. The validator, in the grounded block (`source_schemas` non-empty): for every hub of the model
   not pre-existing and every declared table the hub binds (`hub_binds_to_source_table`), if the
   unread payload is non-empty and **no satellite of the model reads the table at all**, raise
   `E_HUB_PAYLOAD_UNREAD` on the hub with a remedy naming the table, the columns and the parent
   (the hub; or, when the table is a relationship table — it declares two or more foreign keys —
   the link that reads it). A table some satellite reads is never refused here, even if it reads
   only part of the payload: partial coverage is the modeler's choice and the reviewer's business,
   a table nobody reads is a loss.
3. No retirement, no memory: the remedy asks for a construct to be added, and a model that adds
   it passes; the gate is idempotent across attempts.
4. A table whose columns are all keys and foreign keys (a pure association) has no payload and
   is never refused.

## 3 Guards before the change

1. On a fixture cut from the eighth chain's step 3 (`TransactionHistory` keyed `TransactionID`
   with a foreign key to `Product`, `hub_transaction`, `hub_product` with its satellite,
   `link_transaction_product`): `E_HUB_PAYLOAD_UNREAD` on `hub_transaction` naming
   `TransactionHistory` and exactly the payload columns (not `TransactionID`, not `ProductID`);
   the issue carries a remedy naming `hub_transaction`.
2. The same model with a satellite on `hub_transaction` reading the table — or with a satellite
   on `link_transaction_product` reading it (the e-mail shape) — raises nothing.
3. A hub bound to a table whose only non-key columns are declared foreign keys raises nothing.
4. A hub whose table is not declared in `source_schemas` (an earlier increment's) raises nothing.
5. `unread_payload` lists the columns in declared order, normalised comparison.

## 4 Pre-registration

On the next chain: no hub without any satellite reading its table survives a step's final
report; `W_HUB_NO_SAT` may still name hubs whose payload sits on a link satellite (the invention
clause counts those). The gate fires in attempt 1 where the modeler omits a table's payload and
the modeler builds the satellite in attempt 2; a step whose three attempts cannot satisfy it is
red on this class, and that is the design. Decisions may fall by the omitted hubs' warnings.

## 5 Not in this WP

A remedy for a link with one hub (the quota-history shape, the second proposal of 2026-10-07);
a judgement of partial payload coverage; brownfield hubs of earlier increments.

## 6 Results

*(appended after the change)*

**2026-10-07 — refinement before the change landed (§2.1).** A column that another declared
table's foreign key *references* is an identifier, not payload — found on `demo/fk_links_postgres`,
where `hub_sales_order` on `SalesOrderNumber` would have been refused for `SalesOrderID`, the
surrogate `SalesOrderDetail` points at (likewise `hub_location` for `LocationID`). `unread_payload`
takes the declared tables and excludes those columns; a sixth guard pins it.

**2026-10-07 — built; keyless and on PostgreSQL.** Commits `6c93cb6` (guards, failing on import)
and `1a7bddc` (the change; a mypy name clash fixed in the docs commit). `rules.unread_payload`,
`rules.satellite_reads_table`, `rules.hub_payload_remedy`; the validator raises
`E_HUB_PAYLOAD_UNREAD` in the grounded block for hubs of the increment. Guards 1–5 and the
refinement guard pass; 1152 tests, ruff, mypy. The gate refused four hubs of the fk_links demo
(`ShoppingCartItem`: ShoppingCartID, Quantity; `BusinessEntity`: ModifiedDate; `ContactType` and
`Currency`: Name) — a capture of link proposals that had never carried their payload. Four
satellites added to the demo (reading the hub's own relation, so no new stage), the project
regenerated and **built on local PostgreSQL 16: `PASS=134 WARN=0 ERROR=0` (130 before)**. §4's
chain half is **not yet measured live**.

**2026-10-08 — ninth live chain** (`20261008T005807208141Z`, `docs/log.md` 2026-10-08): the gate's first live fire —
step 3 attempt 1, a hub on `TransactionHistoryArchive` with no satellite reading it; the modeler
added the satellite in attempt 2. **Zero satellite-less hubs in every final report**, the
invention clause held for the first time at 0 (it had never been below 1). §4 met.
