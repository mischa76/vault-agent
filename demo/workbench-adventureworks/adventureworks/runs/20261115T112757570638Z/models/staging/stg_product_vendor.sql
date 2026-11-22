-- Generated AutomateDV staging model for the raw-vault constructs on 'product_vendor'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_vendor_via_product'
derived_columns:
  VENDOR_BUSINESSENTITYID: 'BUSINESSENTITYID'
null_columns:
  optional:
    - 'PRODUCTNUMBER'
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  VENDOR_BUSINESSENTITY_HK: 'VENDOR_BUSINESSENTITYID'
  UNITMEASURE_HK: 'UNITMEASURECODE'
  LINK_PRODUCT_VENDOR_HK:
    - 'PRODUCTNUMBER'
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
