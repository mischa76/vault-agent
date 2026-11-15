-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_person_sales_territory'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_person_sales_territory_via_salesterritory'
derived_columns:
  SALES_PERSON_BUSINESSENTITYID: 'BUSINESSENTITYID'
null_columns:
  optional:
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'NAME'
hashed_columns:
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  SALESTERRITORY_HK: 'NAME'
  LINK_SALES_PERSON_SALES_TERRITORY_HK:
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
