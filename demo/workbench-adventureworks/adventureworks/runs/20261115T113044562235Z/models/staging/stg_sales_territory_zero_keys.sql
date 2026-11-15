-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_territory'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: generated — zero_keys_sales_territory, WP86).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'zero_keys_sales_territory'
hashed_columns:
  SALESTERRITORY_HK: 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
