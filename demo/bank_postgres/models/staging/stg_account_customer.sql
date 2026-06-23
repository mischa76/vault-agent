-- Hand-authored AutomateDV staging model (spec §6) for the ownership-over-time table.
-- Computes both hub hash keys plus the link hash key (a multi-column hash), and carries
-- the EFFECTIVE_FROM / EFFECTIVE_TO dates the effectivity satellite needs.
--
-- APPLIED_DTS is a derived copy of EFFECTIVE_FROM: the generated eff_sat sets src_eff to a
-- DEDICATED column (rules.EFFECTIVITY_APPLIED_COLUMN), distinct from src_start_date, so
-- AutomateDV's incremental SQL no longer projects the same column twice (the Postgres
-- "specified more than once" fix). Carrying the start-date value means end-dating closes a
-- superseded record to the business effective date of its successor. (A future staging
-- generator would emit this automatically for eff_sat parents.)
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'raw_account_customer'
derived_columns:
  APPLIED_DTS: 'EFFECTIVE_FROM'
hashed_columns:
  ACCOUNT_HK: 'ACCOUNT_NUMBER'
  CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'
  LINK_ACCOUNT_CUSTOMER_HK:
    - 'ACCOUNT_NUMBER'
    - 'NATIONAL_CUSTOMER_ID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}
with staged as (
{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
)
select * from staged
-- Optional single-batch filter so the effectivity satellite's auto end-dating can be
-- demonstrated across two incremental loads (demo README → "Phase B2"). Each batch is a
-- *snapshot* of the ownership rows loaded on that date — NOT cumulative — so that when the
-- transfer batch arrives the superseded relationship is absent from the source and AutomateDV
-- closes it. Run `--vars '{load_batch: "2026-01-01"}'`, then `--vars '{load_batch: "2026-04-01"}'`.
-- Without the var the filter is inert and every ownership row is staged, so `dbt build` loads
-- the full history in one pass.
{% if var('load_batch', none) is not none %}
where LOAD_DATETIME = '{{ var("load_batch") }}'
{% endif %}
