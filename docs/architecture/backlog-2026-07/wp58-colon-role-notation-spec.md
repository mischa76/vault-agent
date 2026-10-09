---
type: spec
status: not-measured
updated: 2026-10-09
---

# WP58 — `hub:role` in `connected_hubs` is a role-qualified participation

Status: **Approved and in progress** (2026-10-09, user: „super, machen wir 1,2 …“) · Owner:
Mischa Eismann · Author: Claude. Touches `Link`'s hub-reference coercion in `state.py`. A parser
widening to the project's own notation; no prompt change, no model call.

## 1 Problem, measured

Tenth chain, `20261008T223946700186Z`, step 5 attempt 1 (`docs/log.md` 2026-10-09): the modeler
emitted `link_sales_order_address` with `hub_address:ship_to` and `link_currency_rate_currency`
with `hub_currency:from` and `hub_currency:to` in `connected_hubs`. The parser coerced each string
to an unqualified reference whose hub is literally `hub_address:ship_to`, found no such hub and
dropped both links — two real relationships lost as `dropped_record`s. The prompt teaches the
colon form for `driving_key` („name a role-qualified participation as `hub_account:counterparty`“)
and the dict form for `connected_hubs`; the notation is the project's own, used in the same
construct one field over.

## 2 The rule

**A plain string `name:role` in `connected_hubs` is `LinkHubRef(hub=name, role=role)`.**
`Link._normalise_hub_refs` (and the defensive `hub_refs` property) split on the first colon;
a string without a colon stays an unqualified reference, a dict passes through as before. The
split is the same one `resolve_driving_refs` already applies to `driving_key`, so the two fields
read one notation. Empty name or empty role is left as it was (an invalid name the gates refuse).

## 3 Guards before the change

1. `Link(connected_hubs=["hub_address", "hub_address:ship_to"]).hub_refs` is an unqualified and a
   `ship_to`-qualified reference to `hub_address`; a dict form beside it is unchanged.
2. The modeler's parser keeps a link emitted as `["hub_currency:from", "hub_currency:to"]` with
   two role-qualified participations and no `dropped_record`.

## 4 Pre-registration

On the eleventh chain: no `dropped_record` for a link whose only unknown hubs are `name:role`
strings; links the modeler writes in colon form reach the validator with their roles.

## 5 Not in this WP

Teaching the prompt one form (both are now read); roles in `driving_key` (already read).

## 6 Results

*(appended after the change)*

**2026-10-09 — built, keyless.** Commits `5b64d32` (guards, failing) and `64b2143` (the change).
`Link._ref_from_string` in the before-validator and `hub_refs`. Guards 1–2 pass: the tenth chain's
`["hub_currency:from", "hub_currency:to"]` link survives parsing with its two roles, no
`dropped_record`. 1166 tests, ruff, mypy. §4 is **not yet measured live**.
