-- Generated AutomateDV staging model for the raw-vault constructs on 'credit_card_business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_credit_card_business_entity_via_creditcard'
null_columns:
  optional:
    - 'CARDNUMBER'
    - 'BUSINESSENTITYID'
hashed_columns:
  CREDITCARD_HK: 'CARDNUMBER'
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  LINK_CREDIT_CARD_BUSINESS_ENTITY_HK:
    - 'CARDNUMBER'
    - 'BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
