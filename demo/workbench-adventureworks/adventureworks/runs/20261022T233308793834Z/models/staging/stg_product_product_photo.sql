-- Generated AutomateDV staging model for the raw-vault constructs on 'product_product_photo'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductProductPhoto'
derived_columns:
  PRIMARY_:
    source_column: 'primary'
    escape: true
null_columns:
  optional:
    - 'PRODUCTID'
    - 'PRODUCTPHOTOID'
hashed_columns:
  PRODUCT_HK: 'PRODUCTID'
  PRODUCTPHOTO_HK: 'PRODUCTPHOTOID'
  LINK_PRODUCT_PRODUCT_PHOTO_HK:
    - 'PRODUCTID'
    - 'PRODUCTPHOTOID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
