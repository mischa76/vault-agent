-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_address_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_business_entity_address_details_via_addresstype'
derived_columns:
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
null_columns:
  optional:
    - 'BUSINESSENTITYID'
    - 'ADDRESSID'
hashed_columns:
  LINK_BUSINESS_ENTITY_ADDRESS_HK:
    - 'BUSINESSENTITYID'
    - 'ADDRESSID'
    - 'NAME'
  BUSINESS_ENTITY_ADDRESS_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
