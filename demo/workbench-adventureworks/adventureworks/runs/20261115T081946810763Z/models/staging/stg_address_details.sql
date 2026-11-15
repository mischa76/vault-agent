-- Generated AutomateDV staging model for the raw-vault constructs on 'address_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw: 'Address'
derived_columns:
  ADDRESSLINE1__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ADDRESSLINE1 AS text)), ''''), ''UTF8''), ''hex'')'
  ADDRESSLINE2__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ADDRESSLINE2 AS text)), ''''), ''UTF8''), ''hex'')'
  CITY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CITY AS text)), ''''), ''UTF8''), ''hex'')'
  POSTALCODE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(POSTALCODE AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  ADDRESS_HK: 'ADDRESSID'
  ADDRESS_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ADDRESSLINE1__CS'
      - 'ADDRESSLINE2__CS'
      - 'CITY__CS'
      - 'POSTALCODE__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
