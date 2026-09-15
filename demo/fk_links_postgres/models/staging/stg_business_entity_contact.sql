-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_contact'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'BusinessEntityContact'
derived_columns:
  ORGANISATION_BUSINESSENTITYID: 'BUSINESSENTITYID'
  BUSINESSENTITYID: 'PERSONID'
hashed_columns:
  ORGANISATION_BUSINESSENTITY_HK: 'ORGANISATION_BUSINESSENTITYID'
  PERSON_HK: 'BUSINESSENTITYID'
  CONTACTTYPE_HK: 'CONTACTTYPEID'
  LINK_BUSINESS_ENTITY_CONTACT_HK:
    - 'ORGANISATION_BUSINESSENTITYID'
    - 'BUSINESSENTITYID'
    - 'CONTACTTYPEID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
