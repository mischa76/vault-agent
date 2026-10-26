---
type: spec
status: not-measured
updated: 2026-10-26
---

# WP94 — An optional participation whose hub cannot be zero-keyed is a link of its own: the gate and its remedy (C30)

Status: **Approved and in progress** (2026-10-26, the owner's decision on C30 — „as a link of its own" — and the go
to proceed) · Owner: Mischa Eismann · Author: Claude. Backlog C30 (`backlog-2026-10-candidates-3.md`, found by WP93).
Builds on WP83/WP86 (zero keys), WP93 (translations), WP42 (which relation a link reads), WP46 (a remedy with a
retirement the loop follows).

## 1 What is wrong, in one paragraph

AutomateDV's link macro keeps only rows whose foreign-key hashes are all non-NULL (`macros/tables/postgres/link.sql`,
`multikey(fk_cols, condition='IS NOT NULL')`). A participation that is NULL in a source row therefore drops the whole
row — with every other relationship the row carried. WP83 answers that with the zero key, but only where the key
column can hold one: integer and character types. `hub_currency_rate`'s key holds a `timestamp`, so after WP93
`link_sales_order` (nine participations) holds 13 976 of 31 465 orders — the ones with a currency rate — and the
17 489 without one are not in the vault's order link at all, although they have a customer, a territory, addresses,
a ship method. The owner's own model has `link_sales_order_currency_rate` beside the order link; the modeler's unit
of work put the optional participation inside. Nothing today says so: no gate, no remedy, and the catalogue cannot
even state that a column is nullable.

## 2 The rules

1. **The trigger, deterministic.** A link with three or more participations; a participation whose hub's key columns
   are of a *declared* type that is not null-safe (`rules.null_safe_type`; an untyped column is not evidence) — for
   a translated participation the through relation's projected key, for a plain one the columns the link's relation
   carries for it; the relation the link reads is known (WP42), else nothing. Optionality: the relation column's
   `nullable` (new on `SourceColumn`, `None` = unknown; carried by the catalogue) or a profile with `null_ratio > 0`
   gives **`E_LINK_OPTIONAL_PARTICIPANT`** (an error: refuses, feeds the re-model loop); a column declared not
   nullable, or profiled without NULLs, gives nothing; no evidence either way gives
   **`W_LINK_OPTIONAL_PARTICIPANT`** with the same remedy.
2. **The remedy names the link of its own.** `link_<anchor base>_<hub base>` between the anchor — the participation
   whose hub binds the relation the link reads, else the first — and the hub; the big link keeps its other
   participants. The modeler applies it (the prompt reads remedies); the gate creates nothing (ADR-0007). The new
   link reads the same relation: bound by name when named after it, else by the offer or evidence tier, else at
   sign-off (WP82).
3. **Nullability travels.** `SourceColumn.nullable: bool | None`; the catalogue (`dump_source_catalogue`) carries it
   when known; a source-read catalogue (C27) will fill it.

## 3 Not this WP

A zero key for non-character key columns (C30's other way; the owner chose this one). Reading nullability from a
source system (C27). Splitting a link automatically.

## 4 Pre-registration

- **P1** (keyless, the miniature): three participations, the rate's surrogate declared `nullable: true` → the error
  with the remedy naming `link_sales_order_header_currency_rate` and `hub_currency_rate`; `nullable` unknown and no
  profiling → the warning; a profile with `null_ratio > 0` → the error; `nullable: false` → nothing; a two-hub
  link → nothing; the customer's integer participation → never named. Red before the change.
- **P2** (keyless, the demo's last step replayed as WP93 did): the warning on `link_sales_order` naming
  `hub_currency_rate` (the chain's catalogue carries no nullability, no profiling); the error once the column is
  marked nullable. Red before.
- **P3** (local PostgreSQL): the remedy applied by hand to the replayed state — the model the modeler would return —
  regenerated with WP82's bindings (and one for the new stage if no tier binds it), built with zero hand views:
  `link_sales_order` **31 465** (every order; the remaining participants zero-keyed), `link_sales_order_currency_rate`
  **13 976**, every other table equal to WP93's build, both builds passing and idempotent.

## 5 Guards

`tests/test_wp94_optional_participant.py` (P1, P2), committed red before the change.
