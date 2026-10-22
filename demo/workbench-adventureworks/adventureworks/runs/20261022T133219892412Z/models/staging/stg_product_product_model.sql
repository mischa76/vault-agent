-- Generated AutomateDV staging model for the raw-vault constructs on 'product_product_model'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Product'
hashed_columns:
  PRODUCT_HK: 'PRODUCTID'
  PRODUCTMODEL_HK: 'PRODUCTMODELID'
  LINK_PRODUCT_PRODUCT_MODEL_HK:
    - 'PRODUCTID'
    - 'PRODUCTMODELID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
