-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Store'
derived_columns:
  DEMOGRAPHICS: 'CAST(DEMOGRAPHICS AS text)'
  NAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(NAME AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  DEMOGRAPHICS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(DEMOGRAPHICS AS text) AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  BUSINESS_ENTITY_STORE_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'NAME__CS'
      - 'MODIFIEDDATE__CS'
  BUSINESS_ENTITY_STORE_DEMOGRAPHICS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DEMOGRAPHICS__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
