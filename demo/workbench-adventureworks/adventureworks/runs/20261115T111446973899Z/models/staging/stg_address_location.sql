-- Generated AutomateDV staging model for the raw-vault constructs on 'address_location'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'Address'
derived_columns:
  SPATIALLOCATION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SPATIALLOCATION AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  ADDRESS_HK: 'ADDRESSID'
  ADDRESS_LOCATION_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SPATIALLOCATION__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
