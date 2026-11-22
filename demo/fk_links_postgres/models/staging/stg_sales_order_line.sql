-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_line'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_line_via_salesorderheader_and_product'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  PRODUCT_HK: 'PRODUCTNUMBER'
  LINK_SALES_ORDER_LINE_HK:
    - 'SALESORDERNUMBER'
    - 'PRODUCTNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
