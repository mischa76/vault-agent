-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_product_model'
hashed_columns:
  PRODUCTMODEL_HK: 'PRODUCTMODELID'
  PRODUCT_HK: 'PRODUCTID'
  LINK_PRODUCT_MODEL_HK:
    - 'PRODUCTID'
    - 'PRODUCTMODELID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
