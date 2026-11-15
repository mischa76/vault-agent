-- Generated AutomateDV staging model for the raw-vault constructs on 'product_product_subcategory'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_product_subcategory_via_productsubcategory'
null_columns:
  optional:
    - 'PRODUCTNUMBER'
    - 'NAME_VIA_PRODUCTSUBCATEGORY'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  PRODUCTSUBCATEGORY_HK: 'NAME_VIA_PRODUCTSUBCATEGORY'
  LINK_PRODUCT_PRODUCT_SUBCATEGORY_HK:
    - 'PRODUCTNUMBER'
    - 'NAME_VIA_PRODUCTSUBCATEGORY'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
