---
type: spike
status: measured
updated: 2026-10-23
---

# Spike results — a PIT on the owner's vault: AutomateDV's deprecated `pit()` against plain SQL (C22)

Charter: the owner's go of 2026-10-23 for a trial and an ADR, after the correction that AutomateDV 0.11.4
deprecates `pit()` and `bridge()` (`docs/log.md`, 2026-10-23). Measured keyless on PostgreSQL in a throwaway
schema `aw_pit_trial` beside the owner's `aw` (rebuilt the same day with WP89/WP90), dropped afterwards. Decision:
`adrs/ADR-0016-business-vault-pit-bridge.md`.

## Setup

`hub_sales_order` (31 465 keys, one load date 2026-10-18) with its four standard satellites
(`sat_sales_order_amounts`, `_details`, `_payment`, `_status`); an as-of spine of 11 days (2026-10-15 … 25, via
`dbt_utils.date_spine`), so three dates lie before the load (ghost rows) and eight after. Both variants added to a
copy of `workbench/adventureworks/rebuild-20261023/` under `models/business_vault/` (`+schema: pit_trial`), built
with `dbt run --select business_vault` twice from a fresh schema.

- **A — AutomateDV**: `automate_dv.pit(...)` with `materialized='pit_incremental'`, the satellites mapped as
  `{pk: {PK: SALESORDERHEADER_HK}, ldts: {LDTS: LOAD_DATETIME}}`, `stage_tables_ldts: {stg_sales_order: LOAD_DATETIME}`.
- **B — plain SQL**: a dbt `table` model; per hub key × as-of date, each satellite's `MAX(LOAD_DATETIME) <= AS_OF_DATE`
  by one grouped LEFT JOIN per satellite; a missing row becomes a zero key and `1900-01-01`, as A does.

## Measured

| | A: AutomateDV `pit()` | B: plain SQL |
|---|---|---|
| rows | 346 115 (31 465 × 11) | 346 115 |
| first build | 4.67 s | 7.24 s |
| second build | 7.85 s — `INSERT 0 346115`, the whole PIT recomputed and replaced | 8.04 s, full rebuild (table) |
| size | 69 MB | 63 MB |
| ghost rows (as-of before the load) | 3 × 31 465, `LDTS = 1900-01-01` | the same |
| ghost key | `CAST('000…0' AS BYTEA)` — **32 bytes 0x30**, the ASCII zeros | `decode(repeat('0', 32), 'hex')` — 16 zero bytes |
| rows differing (EXCEPT, each way) | 94 395 = exactly the ghost rows, by the ghost key alone | |
| warnings | `DEPRECATED: Since AutomateDV v0.11.0, the pit() and bridge() macros are now deprecated …` on every run | none |

Read in the macro while measuring (`macros/tables/postgres/pit.sql`, 0.11.4): the satellite key is aggregated as
`DECODE(MAX(ENCODE(pk, 'hex')), 'hex')` — a hex round trip per satellite per row; `src_extra_columns` is ignored
with a warning; `enable_ghost_record` is never set in the PostgreSQL macro, so the ghost path is always the literal
one above; the incremental window (`as_of_date_window`) counts a hub row as new when its load date is at or after
the stages' minimum load date — on a vault with one load date that is every row, so the „incremental" run was a full
recompute here and the macro's incremental benefit is **unmeasured**.

## Findings

1. **Both shapes work on the generated vault as it is**: the hub, the satellites and the stage the macro wants
   (`stage_tables_ldts`) exist under the names the generator emits; nothing had to be renamed.
2. **A's ghost key matches nothing**: the vault's hash keys are 16-byte MD5 `bytea`; A writes 32 ASCII zeros. It is
   also not WP86's zero-key hub rows (`-1`/`-2` hash to real MD5s). A consumer joining the PIT to a satellite gets no
   row for a ghost entry either way, but the key is a value no convention of this vault knows.
3. **A is slower on the second run than on the first** and recomputed everything in this measurement; B is a
   full rebuild by construction. Neither has a measured incremental advantage on this data.
4. **A warns on every run** that it is deprecated, by its authors' judgement „not currently fit-for-purpose".
5. **Not measured:** a multi-active satellite under either variant (the PIT stores key and load date; a consumer's
   join then returns every active row of that load — the intended reading, untested); a vault with several load
   dates; Databricks; bridges.

## The two models, as built

```sql
-- A: pit_sales_order_adv.sql
{{ config(materialized='pit_incremental') }}
{%- set yaml_metadata -%}
source_model: hub_sales_order
src_pk: SALESORDERHEADER_HK
src_ldts: LOAD_DATETIME
as_of_dates_table: as_of_dates
satellites:
  sat_sales_order_amounts: {pk: {PK: SALESORDERHEADER_HK}, ldts: {LDTS: LOAD_DATETIME}}
  sat_sales_order_details: {pk: {PK: SALESORDERHEADER_HK}, ldts: {LDTS: LOAD_DATETIME}}
  sat_sales_order_payment: {pk: {PK: SALESORDERHEADER_HK}, ldts: {LDTS: LOAD_DATETIME}}
  sat_sales_order_status:  {pk: {PK: SALESORDERHEADER_HK}, ldts: {LDTS: LOAD_DATETIME}}
stage_tables_ldts: {stg_sales_order: LOAD_DATETIME}
{%- endset -%}
{% set m = fromyaml(yaml_metadata) %}
{{ automate_dv.pit(src_pk=m['src_pk'], src_extra_columns=none, as_of_dates_table=m['as_of_dates_table'],
                   satellites=m['satellites'], stage_tables_ldts=m['stage_tables_ldts'],
                   src_ldts=m['src_ldts'], source_model=m['source_model']) }}
```

```sql
-- B: pit_sales_order_own.sql
{{ config(materialized='table') }}
-- Trial variant B: the same PIT in plain SQL. Per hub key and as-of date, each satellite's
-- latest load at or before that date; a missing row becomes the zero key / 1900-01-01, as the
-- AutomateDV macro does, so the two can be compared row for row.
{%- set sats = ['sat_sales_order_amounts', 'sat_sales_order_details', 'sat_sales_order_payment', 'sat_sales_order_status'] %}
with as_of as (select AS_OF_DATE from {{ ref('as_of_dates') }}),
base as (
    select h.SALESORDERHEADER_HK, a.AS_OF_DATE
    from {{ ref('hub_sales_order') }} h cross join as_of a
)
{%- for sat in sats %},
{{ sat }}_latest as (
    select b.SALESORDERHEADER_HK, b.AS_OF_DATE, max(s.LOAD_DATETIME) as LDTS
    from base b
    left join {{ ref(sat) }} s
      on s.SALESORDERHEADER_HK = b.SALESORDERHEADER_HK and s.LOAD_DATETIME <= b.AS_OF_DATE
    group by b.SALESORDERHEADER_HK, b.AS_OF_DATE
)
{%- endfor %}
select b.SALESORDERHEADER_HK, b.AS_OF_DATE
{%- for sat in sats %},
    case when {{ sat }}_latest.LDTS is null then decode(repeat('0', 32), 'hex') else b.SALESORDERHEADER_HK end as {{ sat }}_PK,
    coalesce({{ sat }}_latest.LDTS, cast('1900-01-01 00:00:00' as timestamp)) as {{ sat }}_LDTS
{%- endfor %}
from base b
{%- for sat in sats %}
join {{ sat }}_latest on {{ sat }}_latest.SALESORDERHEADER_HK = b.SALESORDERHEADER_HK and {{ sat }}_latest.AS_OF_DATE = b.AS_OF_DATE
{%- endfor %}
```
