-- Generated AutomateDV staging model for the raw-vault constructs on 'illustration'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Illustration'
derived_columns:
  DIAGRAM: 'CAST(DIAGRAM AS text)'
  DIAGRAM__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(DIAGRAM AS text) AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  ILLUSTRATION_HK: 'ILLUSTRATIONID'
  ILLUSTRATION_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DIAGRAM__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
