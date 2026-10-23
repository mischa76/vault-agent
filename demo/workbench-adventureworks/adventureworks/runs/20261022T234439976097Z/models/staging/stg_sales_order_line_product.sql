-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_line_product'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderDetail'
null_columns:
  optional:
    - 'SALESORDERID'
    - 'SALESORDERDETAILID'
    - 'PRODUCTID'
hashed_columns:
  SALESORDERDETAIL_HK:
    - 'SALESORDERID'
    - 'SALESORDERDETAILID'
  PRODUCT_HK: 'PRODUCTID'
  LINK_SALES_ORDER_LINE_PRODUCT_HK:
    - 'SALESORDERID'
    - 'SALESORDERDETAILID'
    - 'PRODUCTID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
