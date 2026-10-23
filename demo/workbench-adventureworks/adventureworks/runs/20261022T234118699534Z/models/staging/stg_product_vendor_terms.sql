-- Generated AutomateDV staging model for the raw-vault constructs on 'product_vendor_terms'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductVendor'
null_columns:
  optional:
    - 'PRODUCTID'
    - 'BUSINESSENTITYID'
    - 'UNITMEASURECODE'
hashed_columns:
  LINK_PRODUCT_VENDOR_HK:
    - 'PRODUCTID'
    - 'BUSINESSENTITYID'
    - 'UNITMEASURECODE'
  PRODUCT_VENDOR_TERMS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'AVERAGELEADTIME'
      - 'STANDARDPRICE'
      - 'MINORDERQTY'
      - 'MAXORDERQTY'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
