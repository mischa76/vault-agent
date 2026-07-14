-- Generated AutomateDV staging model for the raw-vault constructs on 'account_customer'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'account_customer'
derived_columns:
  APPLIED_DTS: 'EFFECTIVE_FROM'
hashed_columns:
  ACCOUNT_HK: 'ACCOUNT_NUMBER'
  CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'
  LINK_ACCOUNT_CUSTOMER_HK:
    - 'ACCOUNT_NUMBER'
    - 'NATIONAL_CUSTOMER_ID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
