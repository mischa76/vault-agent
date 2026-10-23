-- Generated AutomateDV staging model for the raw-vault constructs on 'store_sales_person'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_store_sales_person'
derived_columns:
  STORE_BUSINESSENTITYID: 'STOREID'
hashed_columns:
  STORE_BUSINESSENTITY_HK: 'STORE_BUSINESSENTITYID'
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  LINK_STORE_SALES_PERSON_HK:
    - 'STORE_BUSINESSENTITYID'
    - 'SALES_PERSON_BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
