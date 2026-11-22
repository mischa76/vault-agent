-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_description_culture'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_model_description_culture_via_productmodel'
null_columns:
  optional:
    - 'NAME'
    - 'PRODUCTDESCRIPTIONID'
    - 'CULTUREID'
hashed_columns:
  PRODUCTMODEL_HK: 'NAME'
  PRODUCTDESCRIPTION_HK: 'PRODUCTDESCRIPTIONID'
  CULTURE_HK: 'CULTUREID'
  LINK_PRODUCT_MODEL_DESCRIPTION_CULTURE_HK:
    - 'NAME'
    - 'PRODUCTDESCRIPTIONID'
    - 'CULTUREID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
