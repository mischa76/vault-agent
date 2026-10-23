-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_credit_card'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_business_entity_credit_card'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  CREDITCARD_HK: 'CREDITCARDID'
  LINK_BUSINESS_ENTITY_CREDIT_CARD_HK:
    - 'BUSINESSENTITYID'
    - 'CREDITCARDID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
