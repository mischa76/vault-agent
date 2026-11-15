-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_contact'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_business_entity_contact_via_contacttype'
derived_columns:
  PERSON_BUSINESSENTITYID: 'PERSONID'
null_columns:
  optional:
    - 'BUSINESSENTITYID'
    - 'PERSON_BUSINESSENTITYID'
    - 'NAME'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  PERSON_BUSINESSENTITY_HK: 'PERSON_BUSINESSENTITYID'
  CONTACTTYPE_HK: 'NAME'
  LINK_BUSINESS_ENTITY_CONTACT_HK:
    - 'BUSINESSENTITYID'
    - 'PERSON_BUSINESSENTITYID'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
