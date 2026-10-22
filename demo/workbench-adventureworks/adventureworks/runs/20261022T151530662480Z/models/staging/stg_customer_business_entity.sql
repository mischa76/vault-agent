-- Generated AutomateDV staging model for the raw-vault constructs on 'customer_business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Customer'
derived_columns:
  PERSON_BUSINESSENTITYID: 'PERSONID'
  STORE_BUSINESSENTITYID: 'STOREID'
hashed_columns:
  CUSTOMER_HK: 'ACCOUNTNUMBER'
  PERSON_BUSINESSENTITY_HK: 'PERSON_BUSINESSENTITYID'
  STORE_BUSINESSENTITY_HK: 'STORE_BUSINESSENTITYID'
  LINK_CUSTOMER_BUSINESS_ENTITY_HK:
    - 'ACCOUNTNUMBER'
    - 'PERSON_BUSINESSENTITYID'
    - 'STORE_BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
