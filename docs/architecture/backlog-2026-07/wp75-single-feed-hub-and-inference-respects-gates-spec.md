---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP75 — A hub with exactly one feed is not multi-source; the WP56 inference never sets a relation a gate would refuse; one refusal is one review item

Status: **Approved and in progress** (2026-10-17, the owner's go) · Owner: Mischa Eismann
· Author: Claude. From the nineteenth chain (`docs/log.md`, 2026-10-17): step 3 red after three
attempts on `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB`, refusing two history satellites on a hub
whose `sources` list held a single feed; the modeler followed the remedy (dropped
`source_table`) and WP56's backstop put the relation back from the schema — a gate and a
backstop contradicting each other identically in every attempt. No prompt change; the suite
stays keyless.

## 1 The defect, in one paragraph

ADR-0011 narrowed `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` to the one case that is genuinely
inexpressible: a satellite's relation sits *under one of several feeds* and the model cannot
say which. The predicate `source_table_on_multi_source_hub` reads „multi-source“ as
`bool(hub.sources)`, so a hub the modeler declared with one `HubSource` — `hub_product` from
`Product` — is multi-source to it, and `sat_product_cost_history` on `ProductCostHistory` is
refused although there is exactly one feed it could belong to. The gate's remedy says „drop
`source_table`“; the modeler did; `infer_satellite_relation` (WP56) then re-set it from the
schema, because the inference asks the schema and never the gates. Three attempts, three
identical refusals, the mapper skipped, steps 4 and 5 inherit the error. Separately, the
WP73 refusal `binding_rejected` is raised once per staging pass and the mapper's re-bind
appends instead of replacing: one stage, three identical decisions (step 1).

## 2 The rules

1. **Multi-source means two or more feeds.** A new rules helper `hub_is_multi_source(hub)`
   is true for two or more `sources`; `source_table_on_multi_source_hub` is false below
   that, so the gate, the raw-vault generator's defense in depth and the staging generator
   agree that a one-feed hub has no feed ambiguity. A satellite with a foreign relation under
   a one-feed hub (`single_feed_foreign_relation`) is generated like a single-source hub's:
   its own `stg_<sat>` bound verbatim to its `source_table`, hashing the hub's key from the
   canonical column (which, with one feed, is that feed's column) — not split, not flagged.
   `E_SAT_KEY_NOT_IN_SOURCE` keeps judging whether the relation carries that column. A
   one-feed hub's own stage and its split satellites keep WP10's shapes and names.
2. **The inference asks the gate.** `infer_relation` in the modeler sets a relation only
   when the satellite with that relation would pass `source_table_on_multi_source_hub` on its
   (new) parent — on the hub path and on the collapse path alike. A relation the gate would
   refuse is not set and nothing is flagged: the satellite stays as the modeler left it, and
   whatever gate judges a relation-less satellite judges it. No backstop event is emitted for
   withholding — nothing was repaired.
3. **A re-bind replaces its refusals.** The source mapper's re-bind drops the earlier passes'
   `binding_rejected` flags as it already drops `source_binding`, and the result is deduped;
   a stage refused in every pass is one decision.
4. **Records.** The catalogue one-liner, chapter 8 and chapter 12 say „two or more feeds“;
   ADR-0011 is not edited — this spec and the log entry record the refinement.

## 3 Guards before the change

1. The predicate: a one-feed hub with a satellite naming a foreign relation → false; two
   feeds → true (unchanged); `hub_is_multi_source` over zero, one and two feeds.
2. The validator on the nineteenth chain's step-3 shape (`hub_product` with one feed
   `Product`, two history satellites on `ProductCostHistory` and `ProductListPriceHistory`):
   no `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB`; with a second feed added: two.
3. The generators on the same shape: `sat_product_cost_history` rendered once, reading
   `stg_product_cost_history`, which is bound to `ProductCostHistory` and hashes
   `PRODUCT_HK` from `PRODUCTID`; no `GENERATION_GAP` flag; the hub's own stage keeps its
   WP10 name.
4. The modeler (stub extractor) with a two-feed hub and a relation-less satellite whose
   attributes name exactly one declared table that is not a feed: `source_table` stays
   `None`, no `RELATION_INFERRED` flag, no `satellite_relation_inferred` backstop event; the
   same satellite on a one-feed hub is inferred as before.
5. The mapper's re-bind over a state that already carries a `binding_rejected` flag for a
   stage the re-bind refuses again: exactly one such flag afterwards.

## 4 Pre-registration

The twentieth chain, replayed through the nineteenth's step-3 model keylessly first: the
validator passes the two history satellites. Live: the twentieth chain is expected green on
the person-to-sales steps unless a new class appears; `binding_rejected` per step equals the
number of refused stages, not passes.

## 5 Not in this WP

A finer-grain relation under one of *several* feeds (still ADR-0011's inexpressible case);
the review ceiling's record (the nineteenth's 125 stays out).

## 6 Results

*(appended after the change)*
