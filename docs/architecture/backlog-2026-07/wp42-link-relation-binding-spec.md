---
type: spec
status: not-measured
updated: 2026-09-16
---

# WP42 — A link's relation, resolved by more than its name

Status: **Approved and in progress** (2026-09-16, user: „fahre fort mit dem topic 'Links nicht nur
über den Namen an ihre Relation binden'", then „go!") · Owner: Mischa Eismann · Author: Claude.
Depends on WP34 (proposer, `construct_binds_to_source_table`), WP36/ADR-0013 (translation), WP40/WP41
(key licenses, pairing per relation and hub), and `E_LINK_KEY_WRONG_COLUMN` of 2026-09-15.

## 1 Problem, measured

A link is bound to its source relation by its CONSTRUCT NAME. The modeler names links freely, so the
binding misses whenever the name is not the table's: the paid chain of 2026-09-16 built the bill of
materials as `link_bom` (relation `BillOfMaterials`) and `link_currency_rate_currencies` (relation
`CurrencyRate`), each taking one hub twice by role. WP41's pairing never saw them — not because the
pairing failed, but because the link was never bound to a relation. Both keep
`W_ROLE_BK_NOT_IN_SOURCE`, and their stages demand columns no relation carries.

Reach, measured over the 348 links the six persisted `adventureworks_incremental` chains add:

| | links | share |
|---|---|---|
| bound by name today | 84 | 24 % |
| uniquely bindable by the rule below | 219 | 63 % |
| ambiguous — more than one relation fits | 24 | 7 % |
| no relation fits | 21 | 6 % |

Of the 219, **205 are fully pairable** (every participation finds a declared key of that relation)
and 14 only partially.

## 2 The rule — two tiers, and no third

**Tier 1, name.** Exactly one declared relation whose table the link's construct name binds
(`construct_binds_to_source_table`). Unchanged behaviour, tried first.

**Tier 2, offer.** Otherwise: a relation *offers* the hubs built from it
(`hub_binds_to_source_table`) plus the hubs its single-column foreign keys resolve to
(`resolve_fk_target` — WP34/36/39's one rule), counted with multiplicity. A relation fits when its
offer covers the link's participations as a multiset. Exactly one fitting relation binds; two or more
bind nothing.

**Why a satellite's `source_table` is NOT a tier.** It was the obvious third source and it is
measurably wrong: over the same corpus it resolves 1 of the 24 ambiguous cases, and in one case it
contradicts a unique tier-2 match (`link_transaction_product`: the satellite names
`ProductCostHistory`, the offer names `TransactionHistory`). A source that disagrees once in seven
may inform a human, but it must not set a binding.

**Multiplicity is the point, not decoration.** `PurchaseOrderHeader` offers Employee, Vendor,
ShipMethod and its own purchase-order hub; a link taking two of them fits. `BillOfMaterials` offers
`hub_product` twice (two declared keys into `Product`) and `hub_unit_measure` once, which is exactly
what `link_bom` takes.

## 3 Where the resolved relation is used

One helper in `rules/` (`resolve_link_relation`), three call sites, no fourth:

1. the key-license repair (`apply_key_licenses`) — which link reads a licensed table;
2. `E_LINK_KEY_NOT_IN_SOURCE` — which relation an alias or translation is checked against;
3. `E_LINK_KEY_WRONG_COLUMN` — likewise, so the wrong-entity signature is visible on links whose
   name never matched.

## 4 Guards before the change

`tests/test_wp42_link_binding_guard.py`, committed first, on the WP41 miniatures under a name that
does not match the relation. FLIPPED by WP42: (1) `link_bom` gets no repair today and raises two
`W_ROLE_BK_NOT_IN_SOURCE`; (2) a wrong-column participation on a name-unbound link is unnoticed
today. NEVER flipped: (3) two fitting relations bind nothing; (4) a relation that does not offer
every participation binds nothing; (5) nothing is built that the modeler did not build.

## 5 Acceptance

Keyless: the flips and counter-cases; the helper's tiers in isolation. Replay, zero cost, over the
six chains: repairs that newly fire, role warnings that vanish, and every gate code before/after —
**the gates getting stricter on 219 links is the expected direction, and a step that goes red for a
shape the repair cannot fix is a finding to record, not to smooth over.** Postgres: the demo gains a
link whose name does not match its relation; `dbt build` green with the rows joining the right
entities. Live: the user's call, pre-registered after the replay.

## 6 Not in this WP

Staging binding stays as it is — `bind_sources` keeps inferring `raw_<base>` and flagging it; letting
staging read the resolved relation changes generated SQL and deserves its own decision after this
replay. The 24 ambiguous and 21 unbindable links stay unbound. And the modelling defect underneath
some of them is out of scope: in 14 steps the model carries **two hubs on one source entity**
(`hub_vendor` on `AccountNumber` beside `hub_vendor_business_entity` on `BusinessEntityID`), so a
declared key resolves to one hub while the link connects the other.
