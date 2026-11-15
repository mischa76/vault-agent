-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_illustration'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_model_illustration_via_productmodel'
null_columns:
  optional:
    - 'NAME'
    - 'ILLUSTRATIONID'
hashed_columns:
  PRODUCTMODEL_HK: 'NAME'
  ILLUSTRATION_HK: 'ILLUSTRATIONID'
  LINK_PRODUCT_MODEL_ILLUSTRATION_HK:
    - 'NAME'
    - 'ILLUSTRATIONID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
