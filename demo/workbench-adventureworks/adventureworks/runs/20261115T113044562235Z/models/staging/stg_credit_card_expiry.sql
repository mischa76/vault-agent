-- Generated AutomateDV staging model for the raw-vault constructs on 'credit_card_expiry'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'CreditCard'
derived_columns:
  EXPMONTH__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(EXPMONTH AS text)), ''''), ''UTF8''), ''hex'')'
  EXPYEAR__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(EXPYEAR AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  CREDITCARD_HK: 'CARDNUMBER'
  CREDIT_CARD_EXPIRY_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'EXPMONTH__CS'
      - 'EXPYEAR__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
