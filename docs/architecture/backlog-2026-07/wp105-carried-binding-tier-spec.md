---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP105 — A carried binding is the first tier of a link's relation resolution (C38), and the inferred-stage count includes refused bindings (C39)

Status: **Approved and in progress** (2026-10-31, the owner's word: build C38 and C39) · Owner: Mischa Eismann ·
Author: Claude. Both found by the twenty-third chain's keyless PostgreSQL build (`docs/log.md`, 2026-10-31).

## 1 What is wrong, in one paragraph — and where it actually happens

C38 as recorded says the fifth step's offer bound `stg_product_size_unit_measure` and `stg_product_weight_unit_measure`
to `ProductVendor`. The kept outputs say otherwise (read 2026-10-31, chain `20261031T032606335763Z`, steps 3–5
regenerated keylessly through the mapper's re-bind, byte-identical to the kept staging for steps 2–4): **step 3**
bound both stages to `Product` by WP90's evidence tier (`link_binding_evidence`, reason `key`, two review decisions),
and the catalogue carried the binding (`stage_bindings`, WP77). **Step 4** (Purchasing) resolved the two links again
over the increment's tables alone — the offer tier sees only `state.source_schemas` (WP74/WP77, by design) — found
`ProductVendor` the one relation offering `hub_product` (its foreign key `ProductID`) and `hub_unit_measure` (its
foreign key `UnitMeasureCode`, and as the hub's second feed), a unique offer; WP73's check accepted it because WP95's
rule derived the missing role column from that foreign key (`SIZE_UNITMEASURECODE: UNITMEASURECODE`); and
`bind_sources` applies this run's override before the carried binding (WP77 §3). Step 4's project therefore reads the
product's size unit from the **product-vendor** relation — 460 rows at the vendor's grain, the vendor's purchasing
unit instead of the product's size unit — **wrong data, silently, with every gate green.** **Step 5** carried that
binding on; the eval harness does not carry `stage_aliases` between steps (the CLI and the workbench do — C40, recorded
with this WP), and the carried catalogue declares no foreign keys, so WP95 could not derive the column again, WP73
refused the carried `ProductVendor` (`binding_rejected`, 2), and the stages read the `inferred` placeholder: the
build's two errors. The refusal was right by accident. C39 is the instrument's blind spot on the same stages: the eval
counts `SOURCE_BINDING` flags as `stage_refs_inferred` and read 0 for a project with two inferred stages.

## 2 The rules

1. **A carried binding is a tier of the resolution, the first.** `resolve_link_relation` gains two keyword-only
   arguments, `carried_bindings` (`{stage model: relation}`, WP77's field) and `carried_schemas` (WP74's catalogue).
   When the link's stage has a carried binding whose relation is declared in the increment or the carried catalogue,
   the resolution returns that relation with the code `carried`, before the name tier — the order `bind_sources` already
   applies (decided, override, carried, name, inferred). A carried binding naming a relation declared nowhere falls
   through to the tiers as they are. The rule: a binding made in the step whose increment held the evidence — foreign
   keys, keys, the evidence tier's decision — is not overruled by a later step's resolution that cannot see that
   evidence. Only a human (WP82) or a ratified proposal (WP34) changes it, exactly as WP77 §3 ranks them.
2. **Every call site passes the state's carried fields**, so the gates and staging agree on the relation a link reads:
   `link_source_overrides`, `link_binding_evidence_flags`, `link_binding_reasons`, the key repair's `reads` test in
   `apply_key_licenses`, and the validator's two gates that resolve a link's relation. A `carried` resolution produces
   **no override** — `bind_sources` then keeps the carried binding through its own path, WP73-checked; a refused carried
   binding stays a `binding_rejected` decision and does not fall back to the offer (the human binds it, WP82).
   `link_binding_reasons` gives a `carried` link no entry (it is not inferred); `link_binding_evidence_flags` raises no
   decision for it (it was decided when it was made). The precedence inside `bind_sources` is untouched: a ratified
   mapping's or proposal's override and a human's binding still win over a carried binding (WP77's guard).
3. **The stage name rule lives in `rules/`.** `stage_model_name(construct_name)` — `stg_` + the normalised base,
   lower-cased — is promoted from `staging_generator._staging_name` the way `construct_base_name` was (WP34); the
   generators delegate to it. Byte-identical for every valid construct name.
4. **C39: `stage_refs_inferred` counts the stages a human must still bind** — the distinct stage models carrying a
   `SOURCE_BINDING` or a `BINDING_REJECTED` flag — so the eval's number is the written project's. Archived results keep
   their stored numbers; nothing is re-scored.

## 3 Not this WP

C40 — the eval harness loading `carried_bindings` but not `carried_aliases` between steps (`eval/run.py`, both the
run and the resume branch), while `cli.py` and `ui/runs.py` load both: recorded as a candidate, not fixed here; after
rule 1 the measured case needs no alias (`Product` carries the named column). The carried catalogue's missing foreign
and primary keys (`dump_source_catalogue` writes columns only) — WP95's derivation and WP85's grain gate are blind on
carried relations; a candidate when a case needs it. WP95's excuse of an invented alias is unchanged. No paid run: the
regeneration is the measurement.

## 4 Acceptance (keyless)

`tests/test_wp105_carried_binding_tier.py`, committed red: the step-4 shape in miniature (`hub_product` from
`Product`, `hub_unit_measure` fed by `UnitMeasure` and `ProductVendor`, the size link naming `SizeUnitMeasureCode`,
the increment `ProductVendor` with its foreign keys, the carried catalogue `Product` and `UnitMeasure` without keys,
the carried binding to `Product`): the resolution answers `(Product, "carried")`, and `(ProductVendor, "offer")`
without the carried binding; `link_source_overrides` has no entry for the link, and the reasons and evidence flags are
silent; the code generator's pass and the mapper's re-bind leave the stage on `Product` with the named column itself
derived (no alias to `UnitMeasureCode`), no binding flag, and the catalogue carries `Product` on; a carried binding to
an undeclared relation falls through to the offer; a carried relation lacking a hashed column is refused, not replaced
by the offer; the stage name rule in `rules/` equals the generator's; `run_metrics` counts a refused stage and an
inferred stage as two, and one stage with two flags as one. WP77's „this run's override wins" and WP95's demo replay
unchanged.

## 5 Pre-registration (keyless; written before the change, baseline staging of three kept chains dumped first)

- **P1** The twenty-third chain's step 4, regenerated after the change against its regenerated baseline: exactly
  `stg_product_size_unit_measure.sql` and `stg_product_weight_unit_measure.sql` differ, both reading `Product` with
  `SIZE_UNITMEASURECODE: 'SIZEUNITMEASURECODE'` / `WEIGHT_UNITMEASURECODE: 'WEIGHTUNITMEASURECODE'` (step 3's shape);
  `sources.yml` and every other file byte-identical. Falsified by a third differing file.
- **P2** Step 5 regenerated from the **kept** step 4 (the wrong binding carried, no aliases, as the harness ran it):
  both stages still inferred with `binding_rejected: ProductVendor` ×2 — the tier does not repair a wrong carried
  binding; `run_metrics` on that state reads `stage_refs_inferred` 2 (C39; the archived file says 0).
- **P3** Step 5 regenerated from the **regenerated** step 4 (its catalogue re-written by `write_step_vault`, the chain
  as it would run now): both stages bind `Product`, no `binding_rejected`; the project parses and builds on the local
  PostgreSQL copy in a fresh schema PASS=421 of 421 (the kept build: PASS=417, ERROR=2, SKIP=2);
  `link_product_size_unit_measure` 176 rows and `link_product_weight_unit_measure` 205 rows — the products with a
  non-null code (`Product` 504 rows) — every row joining `hub_product` and `hub_unit_measure`.
- **P4** Regression: the 2026-10-30 arms A and T, steps 2–5, and the twenty-third's steps 2 and 3 regenerated after the
  change are byte-identical to their baseline dumps. Falsified by any diff, which is then examined and reported.
- **P5** The suite: WP77's override guard and WP95's demo replay (`_REMAINING`, four stages) pass unchanged; the new
  guards are red before and green after; ruff and bare mypy clean.

## 6 Measured

Appended after the run, with the numbers.
