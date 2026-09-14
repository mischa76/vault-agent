---
type: spec
status: not-measured
updated: 2026-09-14
---

# WP38 — Translated subtype feeds: a table keyed on a surrogate feeds satellites on the hub keyed on the natural key

Status: **Planned** (2026-09-14, user: „plane 2 als nächstes WP") · Owner: Mischa Eismann ·
Author: Claude. Depends on WP29 (resolver, resolution checkpoint, prompt section), WP36
(`KeyTranslation`, the translation view), WP7 §7.1 (`Satellite.source_table`).

## 1 Problem, measured

`hub_sales_representative` appears in every AdventureWorks chain since 2026-08-09 — seven
repeats — and it is not the modeler's invention. Traced on `20260913T230429748887Z`
(`docs/log.md` 2026-09-14): `SalesPerson`'s primary key `BusinessEntityID` is a declared foreign
key to `Employee`; the resolver proposes `sales representative` as `same_as_candidate →
hub_employee` (0.65) with the evidence *"hub_employee is keyed on NationalIDNumber … these cannot
be hashed into the same hub without a mapping table"*; the ratified same-as reaches the modeler
through `render_resolution_prompt_section`, whose sentence for this case is *"keyed differently:
model it as its OWN hub"*. The modeler obeys and says so in the hub's description.

The DV2.0 answer is different: `SalesPerson` is a role of an employee — a subtype whose key is
the supertype's surrogate. Its descriptive attributes belong in satellites on `hub_employee`;
there is no second hub. That answer is unbuildable today for one reason: a satellite attaches
through its parent's canonical key column, which must be present in the satellite's relation
(`collect_staging_specs`, the `source_table` branch), and `SalesPerson` carries
`BusinessEntityID`, not `NationalIDNumber`. WP36 closed exactly this gap for **links** with a
translation view; satellites have no such path.

The same gap drives the second symptom of the weekend: the modeler hubs the surrogate
(`hub_vendor_business_entity`, `hub_employee_business_entity`, 3 of 4 such steps on
2026-09-13) because that is the only way it can hang attributes on a surrogate-keyed row. The
collision remedy (`84642b4`) now tells it to drop that hub; this WP gives it the right place
to put the attributes instead.

## 2 The rule — deterministic, ratified, no judgement

A ratified `same_as` resolution `concept (from table T) → hub_X` is a **subtype feed** when
the evidence is declared: `T` carries a single-column foreign key whose column is `T`'s own
key and whose referenced table is one `hub_X` binds (`hub_binds_to_source_table`), and
`hub_X`'s canonical key is not that column (else it is an ordinary feed, WP10). The
translation is the WP36 record: `KeyTranslation(referencing_column=T.key,
through_table=referenced, surrogate_column=referenced key, natural_key_column=hub_X's key)`,
computed by `_translation_target` — one rule for links and satellites, never two.

Consequences, all deterministic:

- **No hub for `T`.** The prompt section's sentence for a subtype feed becomes: *`concept` (from
  `T`) IS `hub_X`, reached through `referenced`: put its descriptive attributes in satellites on
  `hub_X` with `source_table: T`; do not create a hub.* The old sentence ("model it as its OWN
  hub") stays for a same-as **without** declared evidence — a join nobody declared is a guess.
- **Satellites carry the translation.** `Satellite.key_translation: KeyTranslation | None`,
  set by the applier (not the modeler: the field is stripped from the tool schema like
  `LinkHubRef.key_translation`, `_PROPOSER_OWNED_*`) on every satellite whose parent is
  `hub_X` and whose `source_table` is `T`. Staging renders `stg_<sat>_via_<referenced>` — the
  WP36 view, LEFT JOIN on the surrogate, projecting the natural key — and the satellite's
  dedicated stage reads it and hashes `hub_X`'s HK from the projected column. `.yml` tests
  as WP36: `not_null` on the projected key, `relationships` on the surrogate.
- **Gates.** `E_SAT_TRANSLATION_UNRATIFIED`: a satellite translation no ratified same-as
  produced is refused (mirror of the link gate); `E_SAT_KEY_NOT_IN_SOURCE` stays satisfied
  because the key arrives through the view — the gate checks the view's projection, as
  `E_LINK_KEY_NOT_IN_SOURCE` does for links. Nothing hashed changes for any existing shape.
- **Links into the subtype.** A foreign key that references `T` (`SalesOrderHeader.SalesPersonID
  → SalesPerson`) resolves, with no hub for `T`, to `hub_X` through TWO hops (`SalesPersonID` →
  `SalesPerson.BusinessEntityID` → `Employee.NationalIDNumber`). **Out of scope (§6)**: such
  keys stay `no_hub_for_key` skips in this WP, and the prediction below carries the cost.

## 3 Ratification, HITL, staging

No new checkpoint: the resolution checkpoint (WP29) already ratifies the same-as; its evidence
line gains the declared join (*"SalesPerson.BusinessEntityID → Employee.BusinessEntityID;
hub_employee keyed on NationalIDNumber — a subtype feed, translated"*). The review queue
shows the satellite translation as `FlagKind.SAT_TRANSLATION` (one per satellite, not
aggregated — a join through another relation is its own review class, ADR-0013 §3).
`automatedv.yml` records `key_translation.joins` on the satellite's stage, as for links.

## 4 Guards before the change

Committed first, alone: (1) the prompt section's sentence for a ratified same-as is pinned as
today's ("model it as its OWN hub"); (2) a satellite with `source_table` whose relation lacks
the parent's key is pinned as today's staging outcome (the key is demanded from the relation);
(3) every byte-identity fixture (WP7, WP23, WP35, WP36) — a run without a ratified subtype feed
is byte-identical. Pins (1) and (2) are flipped by the WP in its own commit.

## 5 Acceptance

**Keyless.** SalesPerson miniature (`hub_employee` on `NationalIDNumber` in the existing vault;
`SalesPerson` declared with its key and the FK; a ratified same-as): no `hub_sales_*` in the
delta after the applier; the two satellites the modeler emits with `source_table: SalesPerson`
carry the translation; staging renders one `_via_employee` view and both stages read it;
the gates hold; the counter-case (same-as without declared FK) still yields the old sentence
and an own hub; every fixture untouched. **dbt.** `demo/fk_links_postgres` extended by a
subtype table keyed on the surrogate feeding a satellite on the natural-key hub; `dbt build
--full-refresh` green, the satellite's rows join the hub (queried). **Live, on the user's word,
one chain (~$6.5).** Pre-registered: `hub_sales_representative` absent; zero-satellite hubs
≤ 2; review below 619; cross-domain links **15–16** against 17 on the last chain — the two
links that today attach to the sales-representative hub (`link_sales_order_representative`,
`link_store_sales_representative`) need the two-hop translation of §6 and will be skips.
That trade is the honest price of §6; if the user wants the links kept, §6 comes first.

## 6 Not in this WP

Two-hop translations (a key into a subtype table); changing `E_DUP_HUB`; the business-key
identifier's second candidate (the remedy handles the symptom); Business Vault same-as links;
any change to how the resolver proposes.

## 7 Files

`state.py` (`Satellite.key_translation`, `FlagKind.SAT_TRANSLATION`), `link_proposal.py` or a
new `subtype_feed.py` (the applier: same-as → feed, translation on satellites),
`agents/entity_resolver.py` (`render_resolution_prompt_section`, the evidence line),
`agents/dv2_modeler.py` (schema strip), `agents/staging_generator.py` (satellite branch of
`collect_staging_specs`, `build_staging`'s translation loop generalised to any spec),
`agents/validator.py` (the two gates), `cli.py` (checkpoint note), `eval/run.py` (metrics),
`demo/fk_links_postgres/`, manuals 7 and 9, CHANGELOG, index, log.

## 8 Addendum 2026-09-14 — built, keyless and on Postgres; what the build corrected

Built the same day: guard `ccdb548` (four pins, two flipped by the feature), feature `25bfffc`,
demo `e8a85c2`, and a prerequisite `535610a`. Four corrections to §1–5:

1. **A prerequisite the spec did not see.** In brownfield mode the modeler's parser dropped any
   satellite whose parent is an existing hub — and every modeler link into the existing vault
   (`docs/log.md` 2026-09-14). The satellites §2 relies on would never have reached the applier.
   Fixed first, with its own guard.
2. **The subtype table is not in the concept.** The resolver keys a concept `entity::field` with a
   business label (`sales representative`), never a table. `subtype_feed` derives the table from
   the declared foreign keys: exactly one table with a single-column key on the concept's field
   into a table the target hub binds, not itself carrying the hub's key. None or several: no feed.
3. **§2 named a gate that did not exist.** Nothing checked a satellite's `source_table` for its
   parent's key. `E_SAT_KEY_NOT_IN_SOURCE` was built here, narrowly: translated satellites only,
   so no other run changes outcome.
4. **§5's link prediction is withdrawn.** "15–16" was written before the parser fix; that fix
   keeps modeler links into the vault that the applier used to half-replace. Revised below.

**Verified.** Keyless: 979 passed, ruff, bare mypy; 14 WP38 tests (detection and its two declines,
ratification, applier and flag, schema strip, both gates, metadata, result file). On recordings:
over the persisted vault and real sales schema of `20260913T230429748887Z`, with the recorded
resolver answer, detection fires on `SalesPerson → hub_employee` through `Employee` and on
nothing else — `Store`'s same-as keeps its own-hub sentence because `Store` carries the hub's
key. On PostgreSQL 16: the demo's `dbt build --full-refresh` `PASS=35`, both satellite rows join
`hub_employee`, a second build green, an orphan surrogate fails both view tests.

**Not verified.** Whether the modeler follows the sentence (no paid run). Two hops stay out: in
the last chain the modeler also hung `sat_representative_quota_history` (from
`SalesPersonQuotaHistory → SalesPerson`) on the role hub, and the new sentence gives that data no
attachable place — the role hub may survive for it alone.

**Pre-registered for the next chain, which measures three changes at once** (parser fix, WP38,
and the collision remedy of 2026-09-13): `hub_sales_representative` absent, or present carrying
only data from tables that reference `SalesPerson`; zero-satellite hubs ≤ 2; cross-domain links
≥ 17; review load not predicted — more kept modeler links mean more review items, and the bar of
619 may fail for that reason alone, which would be a finding about the bar, not a regression.

## 9 Addendum 2026-09-15 — live once: the pre-registration held, and a two-hop satellite slipped through

Chain `20260914T213855724138Z` at `5f32bdd`, $6.13, 40 min, every gate 1.000. The script that
evaluates §8 was written before the result (scratchpad, `wp38_prereg.py`):

```
P1 HELD      hub_sales_representative absent
P2 HELD      2 zero-satellite hubs (hub_inventory_transaction, hub_shopping_cart)
P3 HELD      21 cross-domain links (>= 17)
P4 reported  review 547 — per step 27 / 61 / 154 / 96 / 209
```

**The mechanism, live.** The sales modeler's resolution section, re-rendered from the persisted
step-4 vault and the recorded resolver answer, carried the subtype-feed sentence for
`sales_representative → hub_employee` and the own-hub sentence for `store` and `customer`. The
modeler emitted no hub for `SalesPerson` and two satellites on `hub_employee` with
`source_table: SalesPerson`; the applier translated both (4 `sat_translation` flags across the
attempts, deduplicated per attempt); their stages read the view and demand nothing their
relation lacks.

**What slipped through.** The modeler also hung `sat_representative_quota_history`
(multi-active, from `SalesPersonQuotaHistory → SalesPerson`) on `hub_employee`. §2's sentence
says such a table "is not joined this way"; the modeler did it anyway. No translation applies
(two hops, §6), the stage demands `NATIONALIDNUMBER` from `SalesPersonQuotaHistory`, which does
not have it, and **no gate refuses it**: `E_SAT_KEY_NOT_IN_SOURCE` as built in §8 checks
translated satellites only. Regenerated from the persisted final model, the validator reports no
error. `dbt build` would fail on that stage. The same shape existed before WP38 for any
satellite with a `source_table` lacking its parent's key; the parser fix and WP38 made the
modeler use it. Also on `hub_employee` now: three modeler links from sales tables
(`link_sales_order_representative`, `link_store_sales_representative`,
`link_representative_territory`), staged from inferred `raw_*` relations with a
`source_binding` flag, as every unbound modeler link is — not new, and not checked at model time.

**Attribution.** Three changes were measured at once. The role hub's absence and the translated
satellites are WP38's by mechanism (the sentence and the applier are the only paths to them).
Zero drops and the 21 links are the parser fix's. The two followed remedies are the remedy's.
Review 547 and the green gates cannot be split among them.
