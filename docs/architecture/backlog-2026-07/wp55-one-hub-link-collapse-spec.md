---
type: spec
status: not-measured
updated: 2026-10-07
---

# WP55 — A link with one hub is that hub's satellite feed

Status: **Approved and in progress** (2026-10-07, user: „Remedy für Links mit nur einem Hub“)
· Owner: Mischa Eismann · Author: Claude. Touches the modeler's parser (`_parse`), a flag kind
and its review role. A **backstop**, not a gate: the shape never reaches the validator — the
parser drops it today — so the repair happens where the drop happens, deterministically, with
telemetry. No prompt change; no model call.

## 1 Problem, measured

Eighth chain, `20261007T041647752430Z`, step 5 attempt 1 (`docs/log.md` 2026-10-07): the modeler
emitted `link_sales_representative_quota_history` with **one** hub (`hub_employee`) and
`sat_sales_representative_quota_details` on it (QuotaDate, SalesQuota, ModifiedDate, read from
`SalesPersonQuotaHistory`). The parser dropped the link („must connect >=2 known hubs“) and
then the satellite („parent is not a known hub or link“): two `dropped_record` disclosures and
a payload gone from attempt 1's model. Attempt 2 happened to re-model it as a satellite on
`hub_employee` — the right shape, reached by the modeler's own correction under other gates'
pressure, not by anything that told it so. A link with one hub is not a relationship; it is a
dated feed of that hub, and its satellites' home is known.

## 2 The rule

**A link with exactly one hub, and that hub known, is collapsed into the hub: its satellites that
declare a relation move to the hub; the link is dropped.**

1. In the parser, after hubs are validated and before links are judged: a link whose `hub_refs`
   has exactly one entry naming a known hub (the delta's or, in brownfield mode, the vault's) is
   not a `dropped_record`. Every satellite whose parent is that link **and that declares a
   `source_table`** is re-parented to the hub, everything else about it unchanged (type, CDK,
   attributes, description). A satellite on it without a `source_table` is dropped as today —
   its relation would otherwise silently become the hub's own, which the modeler did not say.
2. Each move is a `link_collapsed` flag on the satellite (new `FlagKind.LINK_COLLAPSED`, a
   **disclosure** under WP43: the payload kept its meaning and found its home deterministically),
   naming the link and the hub; one `backstop` trace event `one_hub_link_collapsed` per link with
   the hub and the satellites moved.
3. The key gates judge the moved satellite as they judge any satellite on that hub
   (`E_SAT_KEY_NOT_IN_SOURCE` with WP46's remedy, or a licence translation — the demo's
   `sat_sales_person_quota_history` on `hub_employee` is exactly this shape, built on Postgres).
4. A one-hub link whose hub is unknown, or a link with two or more refs of which some are
   unknown, is dropped as today.

## 3 Guards before the change

1. On the eighth chain's step-5 attempt-1 shape (hub_employee; the one-hub link; the quota
   satellite with its relation): the parsed model has no link, the satellite sits on
   `hub_employee` with its attributes and relation intact, one `link_collapsed` flag names the
   link and the hub, no `dropped_record` names either, and one `one_hub_link_collapsed` backstop
   event lists the satellite.
2. A one-hub link whose hub the model does not know is dropped as today, its satellite with it.
3. A satellite on a collapsed link without a `source_table` is dropped as today (a
   `dropped_record`), while a sibling with one moves.
4. `link_collapsed` is a disclosure in the review queue.

## 4 Pre-registration

On the next chain: a one-hub link, if the modeler emits one, leaves no `dropped_record` and
costs no attempt; its satellite appears on the hub in the same attempt's model and faces the key
gates there. If the shape does not occur, untestable.

## 5 Not in this WP

Inferring the satellite's grain (a dated history on a hub is typically multi-active with the
date as dependent child key — the modeler's `split_rationale` says so in words, and the backstop
does not read words); links with two refs to the same hub; a steering line for the modeler.

## 6 Results

*(appended after the change)*

**2026-10-07 — built, keyless.** Commits `e18d114` (guards, failing), `ffd848c` (the change) and
`c4561c5` (the modeler's old single-hub guard re-based on this rule; two long lines in the docs
commit). `FlagKind.LINK_COLLAPSED` (disclosure, group `link-collapsed`), the parser's collapse
with the `one_hub_link_collapsed` backstop event. Guards 1–4 pass on the eighth chain's step-5
attempt-1 shape: the quota satellite sits on `hub_employee` with its relation, one disclosure,
no dropped record. Guard 4 was corrected with the change (`flag_role` takes a flag). 1156 tests,
ruff, mypy. §4 is **not yet measured live**.

**2026-10-08 — ninth live chain** (`20261008T005807208141Z`): fired twice in step 1 attempt 1
(`link_person_email_address`, `link_person_credential`, both on `hub_person`) — and moved nothing,
because both satellites declared no `source_table` (§2.1's conservative half dropped them as
before). Attempt 2, forced by an attribute overlap, re-modelled the payload on `hub_email_address`
and `hub_person` from `EmailAddress` and `Password`. §4's „its satellite appears on the hub in the
same attempt“ therefore **did not hold** on this shape; the rule did what it says. The inference
that would have made it hold — a relation-less satellite whose attributes belong to exactly one
declared table reads that table — is a finding in `docs/log.md` 2026-10-08, proposed, not built.

**2026-10-09 — tenth live chain** (`20261008T223946700186Z`): the first live moves — step 3 collapsed
`link_product_cost_history` and `link_product_list_price_history` (each on `hub_product` alone)
and moved their satellites to `hub_product` with the declared relations `ProductCostHistory` and
`ProductListPriceHistory`; two `link_collapsed` disclosures, no `dropped_record`. §4 held.
