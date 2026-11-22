-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_ship_method'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_ship_method_via_shipmethod'
null_columns:
  optional:
    - 'NAME'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SHIPMETHOD_HK: 'NAME'
  LINK_SALES_ORDER_SHIP_METHOD_HK:
    - 'SALESORDERNUMBER'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
