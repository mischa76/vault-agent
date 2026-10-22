-- Generated AutomateDV staging model for the raw-vault constructs on 'document'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Document'
hashed_columns:
  DOCUMENT_HK: 'DOCUMENTNODE'
  DOCUMENT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DOCUMENTLEVEL'
      - 'TITLE'
      - 'FOLDERFLAG'
      - 'FILENAME'
      - 'FILEEXTENSION'
      - 'REVISION'
      - 'CHANGENUMBER'
      - 'STATUS'
      - 'DOCUMENTSUMMARY'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
