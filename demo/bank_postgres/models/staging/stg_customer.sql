-- Hand-authored AutomateDV staging model (the generator does not yet emit this layer —
-- spec §9). Computes the hash key + hashdiff that hub_customer / sat_customer_details
-- reference, and passes the source columns + LOAD_DATETIME / RECORD_SOURCE through.
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'raw_customer'
hashed_columns:
  CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'
  CUSTOMER_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CUSTOMER_NAME'
      - 'DATE_OF_BIRTH'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}
{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
