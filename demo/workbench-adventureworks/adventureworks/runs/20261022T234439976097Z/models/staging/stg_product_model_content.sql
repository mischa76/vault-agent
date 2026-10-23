-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_content'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'ProductModel'
hashed_columns:
  PRODUCTMODEL_HK: 'PRODUCTMODELID'
  PRODUCT_MODEL_CONTENT_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CATALOGDESCRIPTION'
      - 'INSTRUCTIONS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
