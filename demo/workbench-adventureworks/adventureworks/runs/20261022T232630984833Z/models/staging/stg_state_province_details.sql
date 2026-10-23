-- Generated AutomateDV staging model for the raw-vault constructs on 'state_province_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'StateProvince'
hashed_columns:
  STATEPROVINCE_HK: 'STATEPROVINCEID'
  STATE_PROVINCE_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'STATEPROVINCECODE'
      - 'ISONLYSTATEPROVINCEFLAG'
      - 'NAME'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
