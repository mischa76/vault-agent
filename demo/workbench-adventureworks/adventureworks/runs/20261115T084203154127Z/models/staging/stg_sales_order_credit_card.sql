-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_credit_card'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_credit_card_via_creditcard'
null_columns:
  optional:
    - 'CARDNUMBER'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  CREDITCARD_HK: 'CARDNUMBER'
  LINK_SALES_ORDER_CREDIT_CARD_HK:
    - 'SALESORDERNUMBER'
    - 'CARDNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
