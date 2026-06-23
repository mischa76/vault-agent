-- Hand-authored AutomateDV staging model (spec §6) for the ownership-over-time table.
-- Computes both hub hash keys plus the link hash key (a multi-column hash), and carries
-- the EFFECTIVE_FROM / EFFECTIVE_TO dates the effectivity satellite needs.
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'raw_account_customer'
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
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
)
select * from staged
-- Optional load-window filter so the effectivity satellite can be demonstrated across two
-- batches (see the demo README): `--vars '{load_date: "2026-01-01"}'` first, then
-- `2026-04-01`. Without the var the filter is inert and every ownership row is staged, so
-- `dbt build` loads the full history in one pass.
{% if var('load_date', none) is not none %}
where LOAD_DATETIME <= '{{ var("load_date") }}'
{% endif %}
