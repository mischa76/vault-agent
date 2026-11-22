-- Generated AutomateDV staging model for the raw-vault constructs on 'product_assembly_component'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_assembly_component_via_product_and_product'
derived_columns:
  APPLIED_DTS: 'STARTDATE'
null_columns:
  optional:
    - 'PRODUCTNUMBER'
    - 'COMPONENT_PRODUCTNUMBER'
    - 'UNITMEASURECODE'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  COMPONENT_PRODUCT_HK: 'COMPONENT_PRODUCTNUMBER'
  UNITMEASURE_HK: 'UNITMEASURECODE'
  LINK_PRODUCT_ASSEMBLY_COMPONENT_HK:
    - 'PRODUCTNUMBER'
    - 'COMPONENT_PRODUCTNUMBER'
    - 'UNITMEASURECODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
