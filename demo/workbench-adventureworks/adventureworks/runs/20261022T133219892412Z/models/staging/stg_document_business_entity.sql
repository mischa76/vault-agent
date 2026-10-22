-- Generated AutomateDV staging model for the raw-vault constructs on 'document_business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Document'
derived_columns:
  BUSINESSENTITYID: 'OWNER'
hashed_columns:
  DOCUMENT_HK: 'DOCUMENTNODE'
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  LINK_DOCUMENT_BUSINESS_ENTITY_HK:
    - 'DOCUMENTNODE'
    - 'BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
