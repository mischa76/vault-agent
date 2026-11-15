-- Generated AutomateDV staging model for the raw-vault constructs on 'product_product_photo_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_product_photo_details_via_product'
derived_columns:
  PRIMARY_:
    source_column: 'primary'
    escape: true
  PRIMARY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST("primary" AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
null_columns:
  optional:
    - 'PRODUCTPHOTOID'
hashed_columns:
  LINK_PRODUCT_PRODUCT_PHOTO_HK:
    - 'PRODUCTNUMBER'
    - 'PRODUCTPHOTOID'
  PRODUCT_PRODUCT_PHOTO_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'PRIMARY__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
