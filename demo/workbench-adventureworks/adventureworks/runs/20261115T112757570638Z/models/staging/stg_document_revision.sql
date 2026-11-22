-- Generated AutomateDV staging model for the raw-vault constructs on 'document_revision'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Document'
derived_columns:
  REVISION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVISION AS text)), ''''), ''UTF8''), ''hex'')'
  CHANGENUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CHANGENUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  STATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STATUS AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  DOCUMENT_HK: 'DOCUMENTNODE'
  DOCUMENT_REVISION_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'REVISION__CS'
      - 'CHANGENUMBER__CS'
      - 'STATUS__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
