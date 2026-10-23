-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_person_sales_territory'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_sales_person_sales_territory'
hashed_columns:
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  SALESTERRITORY_HK: 'TERRITORYID'
  LINK_SALES_PERSON_SALES_TERRITORY_HK:
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'TERRITORYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
