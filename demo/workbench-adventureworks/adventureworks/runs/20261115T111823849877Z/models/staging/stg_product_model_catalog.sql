-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model_catalog'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductModel'
derived_columns:
  CATALOGDESCRIPTION: 'CAST(CATALOGDESCRIPTION AS text)'
  INSTRUCTIONS: 'CAST(INSTRUCTIONS AS text)'
  CATALOGDESCRIPTION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(CATALOGDESCRIPTION AS text) AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCTMODEL_HK: 'NAME'
  PRODUCT_MODEL_CATALOG_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CATALOGDESCRIPTION__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
