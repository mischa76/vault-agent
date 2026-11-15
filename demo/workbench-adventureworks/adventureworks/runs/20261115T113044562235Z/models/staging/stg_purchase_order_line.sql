-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_line'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_purchase_order_line_via_product'
null_columns:
  optional:
    - 'PURCHASEORDERID'
    - 'PURCHASEORDERDETAILID'
    - 'PRODUCTNUMBER'
hashed_columns:
  PURCHASEORDERDETAIL_HK:
    - 'PURCHASEORDERID'
    - 'PURCHASEORDERDETAILID'
  PURCHASEORDERHEADER_HK: 'PURCHASEORDERID'
  PRODUCT_HK: 'PRODUCTNUMBER'
  LINK_PURCHASE_ORDER_LINE_HK:
    - 'PURCHASEORDERID'
    - 'PURCHASEORDERDETAILID'
    - 'PURCHASEORDERID'
    - 'PRODUCTNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
