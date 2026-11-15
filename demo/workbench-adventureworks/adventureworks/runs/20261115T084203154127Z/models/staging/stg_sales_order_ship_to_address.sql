-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_ship_to_address'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderHeader'
derived_columns:
  SHIP_TO_ADDRESSID: 'SHIPTOADDRESSID'
null_columns:
  optional:
    - 'SHIP_TO_ADDRESSID'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SHIP_TO_ADDRESS_HK: 'SHIP_TO_ADDRESSID'
  LINK_SALES_ORDER_SHIP_TO_ADDRESS_HK:
    - 'SALESORDERNUMBER'
    - 'SHIP_TO_ADDRESSID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
