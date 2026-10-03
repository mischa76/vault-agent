-- Generated AutomateDV staging model for the raw-vault constructs on 'currency_rate_detail'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'CurrencyRate'
hashed_columns:
  CURRENCYRATE_HK:
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
  CURRENCY_RATE_DETAIL_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'AVERAGERATE'
      - 'ENDOFDAYRATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
