-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'Person'
derived_columns:
  ADDITIONALCONTACTINFO: 'CAST(ADDITIONALCONTACTINFO AS text)'
  DEMOGRAPHICS: 'CAST(DEMOGRAPHICS AS text)'
  PERSONTYPE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PERSONTYPE AS text)), ''''), ''UTF8''), ''hex'')'
  NAMESTYLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(NAMESTYLE AS text)), ''''), ''UTF8''), ''hex'')'
  TITLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TITLE AS text)), ''''), ''UTF8''), ''hex'')'
  FIRSTNAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FIRSTNAME AS text)), ''''), ''UTF8''), ''hex'')'
  MIDDLENAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MIDDLENAME AS text)), ''''), ''UTF8''), ''hex'')'
  LASTNAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LASTNAME AS text)), ''''), ''UTF8''), ''hex'')'
  SUFFIX__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SUFFIX AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  EMAILPROMOTION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(EMAILPROMOTION AS text)), ''''), ''UTF8''), ''hex'')'
  ADDITIONALCONTACTINFO__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(ADDITIONALCONTACTINFO AS text) AS text)), ''''), ''UTF8''), ''hex'')'
  DEMOGRAPHICS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(DEMOGRAPHICS AS text) AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  BUSINESS_ENTITY_PERSON_NAME_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'PERSONTYPE__CS'
      - 'NAMESTYLE__CS'
      - 'TITLE__CS'
      - 'FIRSTNAME__CS'
      - 'MIDDLENAME__CS'
      - 'LASTNAME__CS'
      - 'SUFFIX__CS'
      - 'MODIFIEDDATE__CS'
  BUSINESS_ENTITY_PERSON_CONSENT_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'EMAILPROMOTION__CS'
  BUSINESS_ENTITY_PERSON_SENSITIVE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ADDITIONALCONTACTINFO__CS'
      - 'DEMOGRAPHICS__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
