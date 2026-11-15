-- Generated AutomateDV staging model for the raw-vault constructs on 'document'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Document'
derived_columns:
  DOCUMENTLEVEL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DOCUMENTLEVEL AS text)), ''''), ''UTF8''), ''hex'')'
  TITLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TITLE AS text)), ''''), ''UTF8''), ''hex'')'
  FOLDERFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FOLDERFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  FILENAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FILENAME AS text)), ''''), ''UTF8''), ''hex'')'
  FILEEXTENSION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FILEEXTENSION AS text)), ''''), ''UTF8''), ''hex'')'
  REVISION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVISION AS text)), ''''), ''UTF8''), ''hex'')'
  CHANGENUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CHANGENUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  STATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STATUS AS text)), ''''), ''UTF8''), ''hex'')'
  DOCUMENTSUMMARY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DOCUMENTSUMMARY AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  DOCUMENT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DOCUMENT AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  DOCUMENT_HK: 'DOCUMENTNODE'
  DOCUMENT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DOCUMENTLEVEL__CS'
      - 'TITLE__CS'
      - 'FOLDERFLAG__CS'
      - 'FILENAME__CS'
      - 'FILEEXTENSION__CS'
      - 'REVISION__CS'
      - 'CHANGENUMBER__CS'
      - 'STATUS__CS'
      - 'DOCUMENTSUMMARY__CS'
      - 'MODIFIEDDATE__CS'
  DOCUMENT_CONTENT_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DOCUMENT__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
