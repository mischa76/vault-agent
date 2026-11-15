-- Generated AutomateDV staging model for the raw-vault constructs on 'shift_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_2: 'Shift'
derived_columns:
  STARTTIME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STARTTIME AS text)), ''''), ''UTF8''), ''hex'')'
  ENDTIME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ENDTIME AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SHIFT_HK: 'NAME'
  SHIFT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'STARTTIME__CS'
      - 'ENDTIME__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
