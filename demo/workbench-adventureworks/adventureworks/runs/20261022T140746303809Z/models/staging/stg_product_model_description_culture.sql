-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_description_culture'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'ProductModelProductDescriptionCulture'
hashed_columns:
  PRODUCTMODEL_HK: 'PRODUCTMODELID'
  PRODUCTDESCRIPTION_HK: 'PRODUCTDESCRIPTIONID'
  CULTURE_HK: 'CULTUREID'
  LINK_PRODUCT_MODEL_DESCRIPTION_CULTURE_HK:
    - 'PRODUCTMODELID'
    - 'PRODUCTDESCRIPTIONID'
    - 'CULTUREID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
