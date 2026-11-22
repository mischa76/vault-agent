-- Generated AutomateDV staging model for the raw-vault constructs on 'shopping_cart_item_product'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_shopping_cart_item_product_via_product'
null_columns:
  optional:
    - 'SHOPPINGCARTID'
    - 'SHOPPINGCARTITEMID'
    - 'PRODUCTNUMBER'
hashed_columns:
  SHOPPINGCARTITEM_HK:
    - 'SHOPPINGCARTID'
    - 'SHOPPINGCARTITEMID'
  PRODUCT_HK: 'PRODUCTNUMBER'
  LINK_SHOPPING_CART_ITEM_PRODUCT_HK:
    - 'SHOPPINGCARTID'
    - 'SHOPPINGCARTITEMID'
    - 'PRODUCTNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
