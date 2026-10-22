-- Generated AutomateDV staging model for the raw-vault constructs on 'state_province_country_region'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'StateProvince'
hashed_columns:
  STATEPROVINCE_HK: 'STATEPROVINCEID'
  COUNTRYREGION_HK: 'COUNTRYREGIONCODE'
  LINK_STATE_PROVINCE_COUNTRY_REGION_HK:
    - 'STATEPROVINCEID'
    - 'COUNTRYREGIONCODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
