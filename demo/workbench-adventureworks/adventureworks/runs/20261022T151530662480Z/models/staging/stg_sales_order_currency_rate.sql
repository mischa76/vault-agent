-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_currency_rate'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_sales_order_currency_rate'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  CURRENCYRATE_HK:
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
  LINK_SALES_ORDER_CURRENCY_RATE_HK:
    - 'SALESORDERNUMBER'
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
