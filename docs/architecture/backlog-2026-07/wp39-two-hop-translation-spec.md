---
type: spec
status: not-measured
updated: 2026-09-15
---

# WP39 — Two-hop translation: a key into a hub-less subtype reaches the supertype hub

Status: **Approved and in progress** (2026-09-15, user: „dann im Anschluss 2") · Owner: Mischa
Eismann · Author: Claude. Depends on WP36 (`KeyTranslation`, `_translation_target`, the
translation view), WP37 (`resolve_fk_target`, the applier), WP38 (subtype feeds), and the
widened `E_SAT_KEY_NOT_IN_SOURCE` of 2026-09-15.

## 1 Problem, measured

The paid chain `20260914T213855724138Z` removed `hub_sales_representative` (WP38) — and the
modeler hung `sat_representative_quota_history` from `SalesPersonQuotaHistory` on `hub_employee`,
plus three links from sales tables. `SalesPersonQuotaHistory.BusinessEntityID` references
`SalesPerson.BusinessEntityID`, which references `Employee.BusinessEntityID`; `hub_employee` is
keyed on `NationalIDNumber`. The value is the same surrogate two tables down, but WP36 and WP38
resolve one declared foreign key and stop: `SalesPerson` has no hub, so the key is a
`no_hub_for_key` skip and the satellite's stage demands a column its table lacks (refused since
2026-09-15).

Across all five AdventureWorks schemas there are **20 identity chains** — `A.c → B.k` where `B.k`
is itself a single-column foreign key `B.k → C.x`. In 16 the middle table has a hub, and that hub
already decides. **In exactly 4 the middle table has none** and the end hub is keyed on a natural
key: `SalesOrderHeader.SalesPersonID`, `Store.SalesPersonID`, `SalesPersonQuotaHistory.BusinessEntityID`,
`SalesTerritoryHistory.BusinessEntityID`, all through `SalesPerson → Employee → hub_employee`.
Of the nine satellites the widened gate refuses on that chain, this WP repairs **one**; the other
eight are one-hop satellite translations without a ratification path (candidate WP40, §6).

## 2 The rule — one more hop, only where no nearer hub exists

In `_translation_target` (and therefore in the per-key proposer, the relationship candidate and
the applier, which all use it): when **no hub binds** the referenced table `B`, and `B` is declared
in this increment, and `B` carries **exactly one** single-column foreign key on the referenced
column `k` itself (`B.k → C.x`), the foreign key `A.c → B.k` is resolved as `A.c → C.x`. The
translation that results is WP36's record — `referencing_column A.c`, `through_table C`,
`surrogate_column x`, `natural_key_column` of the hub — rendered as the same view (`A` LEFT JOIN
`C` on `A.c = C.x`). Sound because `B.k → C.x` makes every value of `B.k` a value of `C.x`, and
`A.c → B.k` makes every value of `A.c` a value of `B.k`. One hop only: no recursion, no cycles.

The nearest hub wins, always. A hub bound to `B` is found first and the chain is never followed;
a hub keyed on `A.c`'s referenced column is matched by WP34 before any translation is tried.

**Satellites.** A ratified subtype feed (WP38) for table `T` also covers each declared table `S`
with a single-column foreign key `S.k → T.k` on `T`'s key column **named like it** — the
proxy for "`S` is keyed by the subtype's key", since the catalogue declares no primary keys.
`SalesPersonQuotaHistory.BusinessEntityID` qualifies; `Store.SalesPersonID` does not (a store is not
a row of the salesperson). The applier translates satellites on the feed's hub read from `S`,
through the same two-hop resolution; the prompt sentence names the covered tables instead of
saying "`T` itself only". The gates follow: `E_SAT_TRANSLATION_UNRATIFIED` accepts those
translations, `E_SAT_KEY_NOT_IN_SOURCE` checks the referencing column in `S`.

## 3 Ratification, HITL, staging

Links: unchanged — a two-hop link is a `declared_fk_translated` proposal ratified at the
checkpoint; its evidence names the middle table (*"SalesPerson.BusinessEntityID is itself a
declared foreign key to Employee.BusinessEntityID and no hub is built from SalesPerson"*).
Satellites: licensed by the same ratified same-as as WP38. Staging, metadata, flags: unchanged
machinery; `through_table` is the end table.

## 4 Guards before the change

`tests/test_wp39_two_hop_guard.py`, committed first: (1) `SalesOrderHeader.SalesPersonID` into a
hub-less `SalesPerson` is a `no_hub_for_key` skip today — flipped; (2) a chain whose middle table
has a hub is decided by that hub — never flipped; (3) the subtype sentence covers "`SalesPerson`
itself only" today — flipped. WP38's guard pin "a table that references the subtype is not
translated" is flipped by this WP in its own commit, with the reason. Every byte-identity fixture.

## 5 Acceptance

Keyless: the three guard flips; a two-hop proposal carries the end table as `through_table` and
the middle table in its evidence; a chain with a hub on the middle table, an undeclared middle
table, or two onward keys yields today's outcome; the quota-history satellite on `hub_employee`
is translated and passes both satellite gates; `Store.SalesPersonID` gives a link proposal but no
satellite coverage. On recordings, zero cost: the sales step of `20260914T213855724138Z` replayed
before and after. Postgres: the demo gains a table referencing the subtype and a link from a
header table through it; `dbt build` green. Live, on the user's word: one chain; pre-registered
in an addendum after the replay, not before it.

## 6 Not in this WP

Chains of three or more; composite keys; the eight one-hop satellite translations without a
ratified same-as (candidate WP40 — they need a checkpoint decision of their own); primary-key
declarations in the source catalogue.
