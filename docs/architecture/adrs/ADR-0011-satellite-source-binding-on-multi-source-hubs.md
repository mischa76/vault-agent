# ADR-0011: Satellite source binding on multi-source hubs

**Status:** Accepted (2026-07-29, with one amendment: the acceptance signal in the
implementation sketch was sharpened — see step 5 — because `bank_extension`'s
`validation_gate` is confounded by a second, independent failure cause)
**Date:** 2026-07-29
**Decision makers:** Mischa Eismann

## Context

WP10 gave hubs several source feeds (`Hub.sources`). Its rule for satellites on such a hub
is a **split**: one satellite per feed, each reading that feed's staging model, with
`record_source` telling the rows apart. That is right when the satellite's attributes come
from *every* feed — two systems each carrying their own version of a customer's name and
address.

WP24 then found that a satellite declaring its own `source_table` (WP7 §7.1, "my rows live
in their own, usually finer-grain relation") on a multi-source hub produced a dbt project
that could not build: the split emitted per-source satellites referencing a hashdiff only an
orphaned `stg_<sat base>` computed. WP24 rejected the combination with
`E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` and recorded, in its §5, that giving it real
semantics "needs a modelling decision and an ADR, not a bug fix". This is that ADR.

What made the question urgent is WP23's live `bank_extension` run (2026-07-29, six runs).
Brownfield mode is where the situation stops being exotic: the CRM joins the core banking
system on `hub_customer`, and REQ-107 asks for the CRM's attributes to be historised
separately. The modeler read that correctly and emitted a satellite carrying
`marketing_segment` / `preferred_channel` / `marketing_opt_out` with
`source_table: crm_contact`. The gate rejected it on every run. A steering rule was added
through the WP16 registry telling the modeler not to do this; it did **not** prevent it
(0/3 runs) — a clean datapoint that the model keeps arriving at this shape because the shape
is the natural answer to the requirement, not because the prompt is unclear.

Two facts decide this ADR, and both were measured rather than reasoned about:

**1. The alternative the gate steers to is itself broken for this case.** With
`source_table` left unset — exactly what the steering asks for — the split demands the CRM's
columns from *both* stagings (probe, 2026-07-29):

```
stg_customer_customer:    expects [NATIONAL_CUSTOMER_ID, MARKETING_SEGMENT, PREFERRED_CHANNEL, …]
stg_customer_crm_contact: expects [NATIONAL_CUSTOMER_ID, MARKETING_SEGMENT, PREFERRED_CHANNEL, …]
generated satellites:     sat_customer_marketing_crm_contact, sat_customer_marketing_customer
```

`stg_customer_customer` reads the core banking relation, which has no marketing columns at
all. So the "correct" path produces a satellite over a staging model that cannot project its
own payload. The gate is not protecting a working alternative; both branches are wrong for a
satellite whose attributes exist in only one feed.

**2. DV2.0 canon treats one-satellite-per-source as the normal case, not the exception.**
A satellite is loaded from one source system; a hub integrating several systems carries one
satellite per system, distinguished by `record_source`. Splitting a satellite across feeds
is the special case that happens to work when the same attributes arrive from each. So a
satellite that *names its source* is not an odd request to be tolerated — it is the ordinary
shape, and the pipeline currently has no way to express it.

There is also an existing precedent inside the codebase: WP23 §2.6 grandfathering already
keeps an existing satellite bound to one feed's staging when its hub becomes multi-source,
instead of splitting it. That is the same rule, applied implicitly to the brownfield case.
Making it explicit and available generally is a unification, not a new concept.

## Decision

**Give `Satellite.source_table` real semantics on a multi-source hub when it names one of
that hub's declared feeds: the satellite is generated ONCE, bound to that feed's staging
model. Keep rejecting every other form.**

Three cases, exhaustively:

| Satellite on a multi-source hub | Behaviour |
|---|---|
| No `source_table` | **Unchanged** — WP10 split, one satellite per feed. The attributes are taken to come from every source. |
| `source_table` naming one of the hub's `sources` | **New** — one satellite, bound to that feed's staging, named without a per-source suffix. "Naming a feed" matches by normalised table name and INCLUDES the materialised legacy feed of a grandfathered hub (WP23 §2.4/§2.6) — the brownfield case is the motivating one and must not fall through the match. |
| `source_table` naming anything else | **Still an error**, with a message that says which feeds are available. |

The third row keeps a real ambiguity out: a finer-grain relation *under* one of the feeds
(WP7's original multi-active case, e.g. `crm_contact_address`) would need to say which feed
it belongs to, and the model has no way to express that. Rejecting it is honest; inventing a
binding is not. When that case appears in the wild it gets its own decision.

`E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` therefore narrows rather than disappears: it stops
firing on the case it was never meant to catch and keeps firing on the one it was.
`rules.source_table_on_multi_source_hub()` stays the single point where all three call sites
(validator, code generator, staging generator) ask the question, so they cannot drift.

The WP16 steering rule `no_source_table_on_multi_source_hub` is **deleted** by this decision:
it tells the model to avoid the shape this ADR blesses. Deleting it is also the honest
outcome of its own evidence — it did not work.

## Alternatives considered

**Keep rejecting (status quo).** Cheapest, and wrong: it leaves brownfield mode unable to
express its central scenario, and — per fact 1 — it steers to output that does not build.
The gate would be protecting nothing.

**Infer the binding.** Pick the feed whose declared source columns contain the satellite's
attributes. It would work on grounded runs and guess on ungrounded ones, and this project
does not guess silently (the WP7 source-binding flag, the WP9 mapper's `unresolved`, the
modeler's dropped records are all the same rule). Rejected. Note that the *modeler* may
still use grounding to choose which `source_table` to declare — that is a proposal a human
ratifies, which is a different thing from the generator inventing a binding.

**Model the CRM attributes on their own hub.** Would satisfy the current gate and is bad
DV2.0: it splits one business concept across two hubs and loses the integration the
multi-source hub exists to provide. Rejected on methodology grounds.

**Split, but only into feeds whose staging can supply the attributes.** Requires the same
inference as above, and silently produces a different number of satellites than the model
declares. Rejected.

## Consequences

- (+) Brownfield mode can express its central scenario: a new source system bringing its own
  attributes to an entity the vault already models. Today it cannot, and the live eval case
  fails validation because of it.
- (+) The generated shape matches DV2.0 canon (one satellite per source on an integrated
  hub) instead of approximating it.
- (+) WP23's grandfathering stops being a special case and becomes an instance of the
  general rule.
- (+) No new state field: `source_table` already exists; only its interpretation on a
  multi-source parent changes.
- (neutral) The three-way branch is more behaviour than a flat rejection, so it needs the
  composition-matrix treatment WP24 established — the WP7 × WP8 × WP10 cells that involve a
  multi-source parent all move.
- (−) A satellite bound to one feed and one bound to a finer-grain relation now look alike in
  the model and behave differently. The validator message has to make the distinction
  legible, or the next person hits the third row and does not know why.
- (−) `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB`'s meaning changes while its name stays. Its
  entry in `docs/operations/08-validation-gates.md` and the WP24 spec both need the
  narrowing recorded, or the catalogue will disagree with the code.

## Implementation sketch (for the WP that follows)

1. `rules.source_table_on_multi_source_hub()` gains the feed check: it returns True (still an
   error) only when the named table is **not** among the parent hub's feeds.
2. Code generator: on a multi-source hub, a satellite whose `source_table` names a feed is
   rendered once against `multi_source_staging_name(hub, that_feed, legacy)` — no suffix on
   the satellite name, since there is only one.
3. Staging generator: that satellite's attributes go to **that feed's** spec only, not to
   every per-source spec (this is what fixes the probe above).
4. Delete the `no_source_table_on_multi_source_hub` steering rule; regenerate the prompt
   fixture and update the steering ledger in the same commit (the WP20 precedent).
5. Add the WP24-style composition cells and re-measure `bank_extension` live. The
   acceptance signal, sharpened at acceptance (2026-07-29): **primary** —
   `E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB` no longer fires on the natural brownfield
   shape (the REQ-107 satellite), measured over ≥ 3 runs; that is the outcome this ADR
   owns. `validation_gate = 1.0` is the *hoped* aggregate but is confounded: the live
   runs fail on a SECOND, independent cause (`E_HUB_HK_COLLISION` on
   hub_campaign/hub_employee — a genuine modelling smell this ADR deliberately does not
   address), so a perfect implementation can still show a failing gate. Report both
   numbers; only the primary one decides.

## References

- WP24 spec §2.2 and §5 (the rejection and its deferred decision):
  `docs/architecture/backlog-2026-07/wp24-multi-source-composition-spec.md`
- WP10 spec (the split rule): `docs/architecture/backlog-2026-07/wp10-multi-source-hub-spec.md`
- WP7 §7.1 (`source_table`'s original meaning):
  `docs/architecture/backlog-2026-07/wp7-staging-refinements-spec.md`
- WP23 §2.6 (grandfathering, the implicit precedent) and the live `bank_extension` findings:
  `docs/architecture/backlog-2026-07/wp23-incremental-extension-spec.md`,
  `eval/datasets/bank_extension/dataset.yml`
- Brownfield charter §2 (extensions vs migrations):
  `docs/architecture/backlog-2026-07/incremental-extension-charter.md`
- ADR-0007 (automation scope per layer — why the agent proposes and a human ratifies)
