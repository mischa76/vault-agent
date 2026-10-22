---
type: spec
status: not-measured
updated: 2026-10-22
---

# WP84 — A multi-active satellite bound to one feed of a multi-source hub is generated as `ma_sat` (C11)

Status: **Approved and in progress** (2026-10-22, owner: „… danach soweit wie du alleine kommst", the order
I proposed: C12, then C11) · Owner: Mischa Eismann · Author: Claude. Backlog C11
(`backlog-2026-10-candidates-2.md`), found in the owner's build (`docs/log.md`, 2026-10-22, steps 5–8).

## 1 What is wrong

`code_generator.py`'s ADR-0011 branch — a satellite that names one feed of a multi-source hub — renders
`_render_sat` whatever the satellite's `sat_type`. A multi-active satellite there loses its child-dependent
key: the owner's vault has three (`sat_business_entity_pay_history` on `RateChangeDate`,
`sat_business_entity_email` on `EmailAddressID`, `sat_business_entity_sales_quota_history` on `QuotaDate`),
all plain `automate_dv.sat`; the pay history re-inserted +26, +35, +38, +38 rows on re-runs. Every
multi-active satellite on a single-source hub or a link is a correct, idempotent `ma_sat`
(`_render_satellite`). The feed's staging already passes the child-dependent key through (the ADR-0011
branch of `collect_staging_specs` adds it as a source column) and hashes the payload — the same stage shape
the verified single-source `ma_sat` uses.

## 2 The rule

In the ADR-0011 branch, dispatch on `sat_type`: `multi_active` renders `_render_ma_sat` against the feed's
staging (`src_cdk` = the child-dependent key); a multi-active satellite without a child-dependent key is
flagged `GENERATION_GAP` and not generated, as `_render_satellite` does; `standard` is unchanged.

## 3 Acceptance (keyless)

`tests/test_wp84_feed_bound_ma_sat.py`: a multi-active satellite naming a feed renders `automate_dv.ma_sat`
with `src_cdk` and the feed's staging as `source_model`, metadata `src_cdk`; without a child-dependent key it
is flagged and absent; a standard feed-bound satellite renders byte-identically.

## 4 Pre-registration (keyless `dbt build` on PostgreSQL)

The owner's Sales run regenerated from its `state.json` (as for WP83, typed catalogue, mapper re-bind), built
into a fresh schema `aw_wp84`, then built a second time:

- **P1** the three satellites are `automate_dv.ma_sat` in the generated SQL.
- **P2** first build: `sat_business_entity_pay_history` 316 rows, `sat_business_entity_email` 19 972,
  `sat_business_entity_sales_quota_history` 163.
- **P3** second build: all three `INSERT 0 0`; every other incremental model `INSERT 0 0` except
  `sat_product_assembly_component_details` (C13, not this WP).
- **P4** PASS=334 both times.
