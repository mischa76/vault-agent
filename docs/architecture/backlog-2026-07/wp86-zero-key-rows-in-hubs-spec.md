---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP86 — Zero-key rows in the hubs: a link's zero key points at a hub row (C25, C12 phase 2)

Status: **Approved and in progress** (2026-10-23, owner: „ok ziehs durch in der reihenfolge" — the order: the paid
chain, then C25, C18, C22) · Owner: Mischa Eismann · Author: Claude. Backlog C25.

## 1 What is missing

Since WP83 a link keeps a row whose optional participant is NULL: the stage replaces it with AutomateDV's zero key
`-2` before hashing. No hub carries `hash('-2')`, so an inner join from such a link to its hub drops the row again
and a relationship test would fail. DV2.0 keeps `-1` (required, missing) and `-2` (optional, not applicable) as
records in every hub; AutomateDV's ghost records cover satellites only.

## 2 The rules

1. **Which hubs.** Every hub that a zero-keyed participation (WP83's rule: `null_columns: optional` declared) hashes
   into — and only those; a vault without zero keys stays byte-identical.
2. **The rows.** Per such hub, a generated view `zero_keys_<hub base>` selects two rows — every key column `'-1'` and
   `'-2'` — cast to the class the participation's relation columns were typed (integer → the platform's `bigint`,
   character → its `varchar`), `LOAD_DATETIME` `1900-01-01` (AutomateDV's ghost-record date) and `RECORD_SOURCE`
   `'SYSTEM'`; and a stage `stg_<hub base>_zero_keys` over it hashing the hub key exactly as the hub's own stage does.
   The hash of `CAST('-2' AS bigint)` is the hash of `COALESCE(col, '-2')` on an integer column: both hash the text `-2`.
3. **The hub reads it.** The hub's `source_model` becomes a list ending with the zero-key stage (AutomateDV's hub unions
   a list, as for multi-source hubs, WP10). The code generator applies it after its staging pass, and the mapper's
   re-bind applies it again — link stages are bound by offer only there, so the set of zero-keyed hubs is final only then.
4. Metadata: `staging` carries the zero-key stage (`source_binding: generated`); `hubs.<hub>.source_model` the list.

## 3 Acceptance (keyless)

`tests/test_wp86_zero_key_hubs.py`: for the WP83 shapes, the participating hubs get `zero_keys_*` and
`stg_*_zero_keys` models with the typed casts and the hub's hash; the hub SQL lists the zero-key stage; a hub no
zero-keyed participation reaches is unchanged; the stage's relation resolves at parse time (`unresolved_stage_refs`).

## 4 Pre-registration (keyless `dbt build`, PostgreSQL)

The owner's Sales vault regenerated with WP85's remedy (as `workbench/adventureworks/rebuild-20261022/`) and today's
generator, built twice into a fresh schema:

- **P1** PASS for every node, both builds; second build `INSERT 0 0` for every incremental model.
- **P2** every zero-keyed hub holds exactly two rows more than its non-zero source keys, with business keys `-1`, `-2`.
- **P3** every link row whose participant hash is `hash('-2')` joins its hub: 0 link rows without a hub row across
  all links (was 19 185 for `link_customer_business_entity` alone after WP83).
