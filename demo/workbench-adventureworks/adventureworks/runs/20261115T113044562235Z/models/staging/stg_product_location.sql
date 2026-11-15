-- Generated AutomateDV staging model for the raw-vault constructs on 'product_location'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_location_via_product_and_location'
null_columns:
  optional:
    - 'PRODUCTNUMBER'
    - 'NAME'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  LOCATION_HK: 'NAME'
  LINK_PRODUCT_LOCATION_HK:
    - 'PRODUCTNUMBER'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
