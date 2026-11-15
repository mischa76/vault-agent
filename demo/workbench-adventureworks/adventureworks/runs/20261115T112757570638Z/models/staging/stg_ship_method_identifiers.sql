-- Generated AutomateDV staging model for the raw-vault constructs on 'ship_method_identifiers'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ShipMethod'
derived_columns:
  SHIPMETHODID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SHIPMETHODID AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SHIPMETHOD_HK: 'NAME'
  SHIP_METHOD_IDENTIFIERS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SHIPMETHODID__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
