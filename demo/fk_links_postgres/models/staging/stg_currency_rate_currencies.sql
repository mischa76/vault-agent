-- Generated AutomateDV staging model for the raw-vault constructs on 'currency_rate_currencies'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'CurrencyRate'
derived_columns:
  FROM_CURRENCYCODE: 'FROMCURRENCYCODE'
  TO_CURRENCYCODE: 'TOCURRENCYCODE'
hashed_columns:
  CURRENCYRATE_HK:
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
  FROM_CURRENCY_HK: 'FROM_CURRENCYCODE'
  TO_CURRENCY_HK: 'TO_CURRENCYCODE'
  LINK_CURRENCY_RATE_CURRENCIES_HK:
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
    - 'FROM_CURRENCYCODE'
    - 'TO_CURRENCYCODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
