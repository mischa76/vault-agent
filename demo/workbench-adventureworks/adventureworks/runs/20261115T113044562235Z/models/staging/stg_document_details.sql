-- Generated AutomateDV staging model for the raw-vault constructs on 'document_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'Document'
derived_columns:
  TITLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TITLE AS text)), ''''), ''UTF8''), ''hex'')'
  FOLDERFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FOLDERFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  DOCUMENTLEVEL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DOCUMENTLEVEL AS text)), ''''), ''UTF8''), ''hex'')'
  FILENAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FILENAME AS text)), ''''), ''UTF8''), ''hex'')'
  FILEEXTENSION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FILEEXTENSION AS text)), ''''), ''UTF8''), ''hex'')'
  DOCUMENTSUMMARY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DOCUMENTSUMMARY AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  DOCUMENT_HK: 'DOCUMENTNODE'
  DOCUMENT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'TITLE__CS'
      - 'FOLDERFLAG__CS'
      - 'DOCUMENTLEVEL__CS'
      - 'FILENAME__CS'
      - 'FILEEXTENSION__CS'
      - 'DOCUMENTSUMMARY__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
