-- Generated AutomateDV staging model for the raw-vault constructs on 'address_state_province'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_address_state_province_via_stateprovince'
null_columns:
  optional:
    - 'ADDRESSID'
    - 'NAME'
hashed_columns:
  ADDRESS_HK: 'ADDRESSID'
  STATEPROVINCE_HK: 'NAME'
  LINK_ADDRESS_STATE_PROVINCE_HK:
    - 'ADDRESSID'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
