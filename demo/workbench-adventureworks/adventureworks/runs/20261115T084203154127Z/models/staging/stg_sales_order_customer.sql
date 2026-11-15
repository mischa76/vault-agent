-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_customer'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_customer_via_customer'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  CUSTOMER_HK: 'ACCOUNTNUMBER_VIA_CUSTOMER'
  LINK_SALES_ORDER_CUSTOMER_HK:
    - 'SALESORDERNUMBER'
    - 'ACCOUNTNUMBER_VIA_CUSTOMER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
