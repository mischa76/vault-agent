-- Generated AutomateDV staging model for the raw-vault constructs on 'product_size_unit_measure'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Product'
derived_columns:
  SIZE_UNITMEASURECODE: 'SIZEUNITMEASURECODE'
null_columns:
  optional:
    - 'PRODUCTNUMBER'
    - 'SIZE_UNITMEASURECODE'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  SIZE_UNITMEASURE_HK: 'SIZE_UNITMEASURECODE'
  LINK_PRODUCT_SIZE_UNIT_MEASURE_HK:
    - 'PRODUCTNUMBER'
    - 'SIZE_UNITMEASURECODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
