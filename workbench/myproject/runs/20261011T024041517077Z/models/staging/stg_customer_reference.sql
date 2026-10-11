-- Generated AutomateDV staging model for the raw-vault constructs on 'customer_reference'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'customer'
hashed_columns:
  CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'
  CUSTOMER_REFERENCE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'BANK_CUSTOMER_REFERENCE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
