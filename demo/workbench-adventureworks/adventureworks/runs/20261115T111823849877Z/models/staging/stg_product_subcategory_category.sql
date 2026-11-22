-- Generated AutomateDV staging model for the raw-vault constructs on 'product_subcategory_category'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_subcategory_category_via_productcategory'
null_columns:
  optional:
    - 'NAME_VIA_PRODUCTCATEGORY'
hashed_columns:
  PRODUCTSUBCATEGORY_HK: 'NAME_VIA_PRODUCTCATEGORY'
  PRODUCTCATEGORY_HK: 'NAME_VIA_PRODUCTCATEGORY'
  LINK_PRODUCT_SUBCATEGORY_CATEGORY_HK:
    - 'NAME_VIA_PRODUCTCATEGORY'
    - 'NAME_VIA_PRODUCTCATEGORY'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
