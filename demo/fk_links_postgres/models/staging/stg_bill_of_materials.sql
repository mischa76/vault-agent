-- Generated AutomateDV staging model for the raw-vault constructs on 'bill_of_materials'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_bill_of_materials_via_product_and_product'
hashed_columns:
  ASSEMBLY_PRODUCT_HK: 'ASSEMBLY_PRODUCTNUMBER'
  COMPONENT_PRODUCT_HK: 'COMPONENT_PRODUCTNUMBER'
  UNITMEASURE_HK: 'UNITMEASURECODE'
  LINK_BILL_OF_MATERIALS_HK:
    - 'ASSEMBLY_PRODUCTNUMBER'
    - 'COMPONENT_PRODUCTNUMBER'
    - 'UNITMEASURECODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
