-- Generated AutomateDV staging model for the raw-vault constructs on 'product_lifecycle'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'Product'
hashed_columns:
  PRODUCT_HK: 'PRODUCTID'
  PRODUCT_LIFECYCLE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SELLSTARTDATE'
      - 'SELLENDDATE'
      - 'DISCONTINUEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
