-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_illustration'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'ProductModelIllustration'
hashed_columns:
  PRODUCTMODEL_HK: 'PRODUCTMODELID'
  ILLUSTRATION_HK: 'ILLUSTRATIONID'
  LINK_PRODUCT_MODEL_ILLUSTRATION_HK:
    - 'PRODUCTMODELID'
    - 'ILLUSTRATIONID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
