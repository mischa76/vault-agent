-- Generated AutomateDV staging model for the raw-vault constructs on 'location_capacity_history'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_location_capacity_history_via_location'
hashed_columns:
  LOCATION_HK: 'NAME'
  LOCATION_CAPACITY_HISTORY_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'COSTRATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
