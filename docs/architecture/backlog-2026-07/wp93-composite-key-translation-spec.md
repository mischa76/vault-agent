---
type: spec
status: not-measured
updated: 2026-10-26
---

# WP93 — Composite-key translation: a surrogate reference reaches a hub keyed on several columns through one join; a NULL surrogate is a NULL participant (C28)

Status: **Approved and in progress** (2026-10-26, the owner's go to „proceed as recommended" after WP92; C28 was the
recommendation) · Owner: Mischa Eismann · Author: Claude. Backlog C28 (`backlog-2026-10-candidates-3.md`, found by
WP82). Release criterion 3 (`release-1.0-criteria.md`): „AdventureWorks builds without a hand-made view" — the one
view WP82 left is this shape. Builds on WP36/ADR-0013 (the translation), WP40 (key licenses), WP45 (composite keys),
WP83/WP86 (zero keys).

## 1 What is wrong, in one paragraph

`SalesOrderHeader.CurrencyRateID` references `CurrencyRate.CurrencyRateID`, a surrogate; `hub_currency_rate` is keyed
on `CurrencyRate`'s natural key, three columns (`CurrencyRateDate`, `FromCurrencyCode`, `ToCurrencyCode`). The paid
chain's last step ratified that key as a license (`declared_fk_pending`, accepted) and the applier could not resolve
it: WP36's trigger reads one natural key column (`canonical_hub_key_column`), which for a composite hub is the
*label* (`CURRENCY_RATE`), so the typed skip `translation_key_missing` names a column that was never a column; the
validator refuses „a translation" on a composite hub outright (`E_HUB_COMPOSITE_UNSUPPORTED`); and the staging
generator's composite branch (WP45) hashes the participation over the hub's three columns as if the relation carried
them. The stage `stg_sales_order` — shared by `hub_sales_order` and `link_sales_order` — therefore stays inferred and
needs the one hand view that is a join. A second defect sits underneath: WP36's translation view ships an
unconditional `not_null` test on the projected key, so a *nullable* surrogate (most sales orders have no currency
rate) would fail the build of every model downstream of the view, the hub's included, although a NULL foreign key is
not a dangling reference — it is a NULL participant, the case WP83 zero-keys.

## 2 The rules

1. **The trigger reads the hub's key columns.** `_translation_target` keys on `hub_key_columns(hub)`: one column for
   a single key (unchanged), all of them for a composite. A declared referenced relation must carry the surrogate and
   every key column, else the typed skip names the missing ones. The translation carries `natural_key_columns` (the
   hub's, in hashing order); `natural_key_column` stays the first for every reader that shows one.
2. **The gate admits the translation shape on a composite hub** when the translation's columns are the hub's key
   columns; a role, an alias, or a translation whose columns differ stay refused with the same code.
   `E_LINK_KEY_NOT_IN_SOURCE` checks every projected column on the declared through relation.
3. **Staging hashes the participation over the projected columns.** The translation view (one LEFT JOIN) projects
   every natural key column under the hub's own column names; the link's FK hash and the link hash take them in the
   hub's order, exactly what the hub's own stage hashes. A stage a hub shares reads the view like a link's own stage
   does — the hub's columns pass through `t.*` untouched.
4. **A NULL surrogate is a NULL participant, not a dangling reference.** The view's `not_null` tests hold
   `where: "<surrogate> is not null"`; `relationships` ignores NULL by itself. A translated participation records a
   null group (projected columns ← the surrogate), so a bound stage declares them `null_columns: optional` when the
   surrogate's type is null-safe (WP83) and the hub gets its zero-key row (WP86) — the key column types for that row
   come from the through relation. This applies to single-column translations too; it changes WP36's generated test
   file deliberately (recorded in §4 and the log).
5. **Nothing new is created.** Licenses and proposals resolve through the unchanged applier; the modeler's schema keeps
   `KeyTranslation` stripped (WP36 addendum).

## 3 Not this WP

Composite *foreign keys* (WP46's components, the WP40 pin `test_a_composite_key_stays_a_skip` stays). Two-hop
translation into a composite hub (WP39) — unmeasured. The owner's own build (`raw_sales_order_currency_rate`), not on
this machine. C29.

## 4 Pre-registration

- **P1** (rules 1, 2, 5 — keyless): the proposer on the miniature (`SalesOrderHeader.CurrencyRateID → CurrencyRate`,
  `hub_currency_rate` composite) yields a translated proposal / resolves the license with three natural key columns;
  the gate passes it and still refuses a role on the composite hub. Red before the change.
- **P2** (rules 3, 4 — keyless): the generated project holds `stg_<stage>_via_currencyrate` projecting the three
  columns, the stage reads it and hashes `CURRENCYRATE_HK` over them; the view's tests carry the `where`; a bound
  stage declares the three optional and `zero_key_hubs` names `hub_currency_rate` with `varchar` types. Red before.
- **P3** (the paid chain's last step, replayed keylessly): `apply_key_licenses` on the stored state resolves the
  ratified license to `hub_currency_rate` with the translation and repairs `link_sales_order`; regenerated with WP82's
  seven bindings, **no stage is inferred** (WP82 left one). Red before (the license stays unresolved).
- **P4** (local PostgreSQL, keyless): the regenerated project built **with zero hand views** — both builds pass, every
  incremental model idempotent; against WP82's bound build (PASS=410, one view) the prediction is: every table equal
  except `hub_currency_rate` (+1, its zero-key row) and nothing in `link_sales_order`'s row count (the hand view was a
  LEFT JOIN, the translation view is one); PASS grows by the view, its tests and the zero-key stage.
- **P5** (rule 4 on WP36's own case): the WP36/WP37/WP39/WP40 tests pass with the `where` on the `not_null` test; any
  fixture that pins the old test file is updated in the WP's own commit with this reason.

## 5 Guards

`tests/test_wp93_composite_translation.py` (P1–P3), committed red before the change.

## 6 Addendum 2026-10-26, before the build — P4 revised: no zero key into a datetime-keyed hub

Rule 4 as written assumed the zero key reaches `hub_currency_rate`. It cannot: WP83 §2.2 admits null handling only
where `COALESCE(col, '-2')` is type-safe — integer and character columns — and `CurrencyRateDate` is a datetime; WP86's
zero-key row would cast `'-1'` into the hub's timestamp column. The rule is therefore: a translated participation is
zero-keyed when the surrogate's type **and every projected key column's type in the through relation** are null-safe
(`_group_types`); otherwise the NULL participant stays NULL, exactly as before, and the `where` on the view's
`not_null` tests is what lets the build pass. The guard changed accordingly in the WP's own commit: the datetime case
asserts no null handling and no zero-key hub; a character-keyed composite hub (`CurrencyPair`) asserts both. **P4
revised:** against WP82's bound build every table equal, `hub_currency_rate` included (no zero-key row);
`link_sales_order` equal in rows; PASS grows by the view and its tests. P3 holds as registered: the demo's stage is
bound and inferred stages are zero.
