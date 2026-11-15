-- Generated AutomateDV staging model for the raw-vault constructs on 'state_province_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'StateProvince'
derived_columns:
  STATEPROVINCECODE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STATEPROVINCECODE AS text)), ''''), ''UTF8''), ''hex'')'
  ISONLYSTATEPROVINCEFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ISONLYSTATEPROVINCEFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  STATEPROVINCE_HK: 'NAME'
  STATE_PROVINCE_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'STATEPROVINCECODE__CS'
      - 'ISONLYSTATEPROVINCEFLAG__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
