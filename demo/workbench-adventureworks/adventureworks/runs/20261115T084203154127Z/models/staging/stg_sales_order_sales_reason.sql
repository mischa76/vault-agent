-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_sales_reason'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_sales_reason_via_salesorderheader'
null_columns:
  optional:
    - 'SALESREASONID'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SALESREASON_HK: 'SALESREASONID'
  LINK_SALES_ORDER_SALES_REASON_HK:
    - 'SALESORDERNUMBER'
    - 'SALESREASONID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
