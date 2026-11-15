-- Generated AutomateDV staging model for the raw-vault constructs on 'product_model'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductModel'
derived_columns:
  CATALOGDESCRIPTION: 'CAST(CATALOGDESCRIPTION AS text)'
  INSTRUCTIONS: 'CAST(INSTRUCTIONS AS text)'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  CATALOGDESCRIPTION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(CATALOGDESCRIPTION AS text) AS text)), ''''), ''UTF8''), ''hex'')'
  INSTRUCTIONS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CAST(INSTRUCTIONS AS text) AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCTMODEL_HK: 'NAME'
  PRODUCT_MODEL_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'MODIFIEDDATE__CS'
  PRODUCT_MODEL_CATALOGUE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CATALOGDESCRIPTION__CS'
  PRODUCT_MODEL_INSTRUCTIONS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'INSTRUCTIONS__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
