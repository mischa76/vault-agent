---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP106 — The eval harness carries `stage_aliases` as the product does (C40), and the carried catalogue carries a table's declared keys (C41)

Status: **Approved and in progress** (2026-10-31, the owner's word: C40 and C41) · Owner: Mischa Eismann · Author: Claude.
Both found by WP105 while reading the twenty-third chain's kept outputs (`docs/log.md`, 2026-10-31).

## 1 What is wrong

**C40.** `cli.write_outputs` writes a step's `stage_aliases` into the catalogue and `run --existing` and the workbench
load them back (WP82, WP95); the eval harness does neither: `write_step_vault` writes bindings without aliases, and
`run_case_once` and the resumed-step branch of `run_chain_once` load `carried_bindings` but not `carried_aliases`. An
alias a human typed or WP95 derived reaches the next step in the product and not in a measured chain, where WP73 then
refuses the carried relation for the very column the alias supplied — the twenty-third chain's step 5. The harness
measures a product that is not the one shipped.

**C41.** `dump_source_catalogue` writes a table's columns (types and nullability included) and nothing of its keys:
no `primary_key`, no `unique_keys`, no `foreign_keys`. A relation read from the carried catalogue can therefore not be
judged by WP95's role derivation at binding time — step 5 could not derive `SIZE_UNITMEASURECODE` on the carried
`ProductVendor` where step 4 could. The reader (WP96) and the derivation (WP85) carry all three in the house format;
the catalogue loader already *is* the house-format reader (`load_existing_catalogue` → `load_source_schemas`), so
writing the keys is the whole change.

## 2 The rules

1. **The catalogue carries the declared keys, in the house shape, only where declared.** After `columns`, `schema`,
   `database`: `foreign_keys` (each `columns`, `references_table`, `references_columns`, and `references_schema` when
   set), `primary_key`, `unique_keys` — the order `eval.adventureworks.derive` writes. A table without them renders
   byte-identically (WP83's pin). What the catalogue still does not carry stays as decided: the table and column
   comments (WP97) and `inferred_keys` (WP99) — the carried tables reach staging only, never a model.
2. **Who reads the carried keys.** `bind_sources` (WP73's check with WP95's derivation on a carried relation) and
   nothing else: the validator's gates and the evidence tier read `state.source_schemas` (the increment) at both
   sites, so WP85's grain gate and the key clause are unchanged — the gates' declared tables stay the increment's, as
   WP74 §2 drew the line. Named here so nobody reads a wider effect into the change.
3. **The harness writes and loads aliases exactly as the CLI does.** `write_step_vault` passes
   `stage_aliases(staging metadata)` to the writer; `run_case_once` and the resumed-step branch set
   `carried_aliases=load_carried_aliases(existing)`. One source of truth for "what a step hands the next" would be
   better than four call sites — not this WP; the four are listed here so the next one finds them.

## 3 Not this WP

A `carried_step(path)` helper unifying the four load sites (CLI, workbench, harness run, harness resume). WP85's
grain gate on carried relations. Re-scoring any archived chain.

## 4 Acceptance (keyless)

`tests/test_wp106_carried_keys_and_aliases.py`, committed red (five of six; the byte pin green): the catalogue
renders primary, unique and foreign keys in the house shape and key order; the loader reads them back through
`write_step_vault`; a keyless table is byte-identical; WP95's miniature derives `SALES_PERSON_BUSINESSENTITYID` on a
`SalesPerson` carried *through the catalogue* (refused today); `write_step_vault` writes the aliases `load_carried_aliases`
reads; `run_case_once` on a stubbed graph hands the step the previous step's bindings and aliases.

## 5 Pre-registration (keyless; written before the change)

- **P1** The twenty-third chain's step 4, regenerated as for WP105 and written by `write_step_vault`: the catalogue
  declares the keys of the 49 tables of Person, HumanResources, Production and Purchasing — 49 with a primary key, 18
  with unique keys, 31 with foreign keys (57 keys) — and `stage_aliases` where the staging metadata has them (none for
  the two product→unit-measure stages, which read the named column itself since WP105).
- **P2** The chain re-chained keylessly from the kept step 1 model (each step's model from its kept `dv_model.yml`,
  its mappings from the result file, the previous step always the *regenerated* one, written by `write_step_vault`):
  `stage_refs_inferred` 0 and no `binding_rejected` on any step; both product→unit-measure stages on `Product` in steps
  3–5; step 5's staging equal to WP105's P3 regeneration (the three files P1 of WP105 named against the kept project,
  nothing else), the fifth project parses and builds on PostgreSQL PASS=421 of 421 with the two links as WP105 measured
  (504 rows each, 176 / 205 on real units). Any further difference is reported, each explained.
- **P3** Step 5 from the **kept** step 4 with its aliases loaded as the harness now loads them: the carried
  `ProductVendor` passes WP73 with the carried alias and both stages bind it — the alias travels as in the CLI. With
  WP105 upstream the chain no longer produces that binding (P2); this is the mechanism, not a repair.
- **P4** Arms A and T and the twenty-third's steps 2–5 regenerated from their kept directories (which carry no keys)
  are byte-identical to WP105's regenerations: C41 changes what is *written*, not how a kept catalogue is read.
- **P5** Suite green, ruff, bare mypy; WP83's byte pin, WP97's and WP99's „not carried" pins unchanged.

## 6 Measured

Appended after the run.
