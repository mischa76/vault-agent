-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_person_territory_history'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_person_territory_history_via_salesterritory'
derived_columns:
  APPLIED_DTS: 'STARTDATE'
null_columns:
  optional:
    - 'BUSINESSENTITYID'
    - 'NAME'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  SALESTERRITORY_HK: 'NAME'
  LINK_SALES_PERSON_TERRITORY_HISTORY_HK:
    - 'BUSINESSENTITYID'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
