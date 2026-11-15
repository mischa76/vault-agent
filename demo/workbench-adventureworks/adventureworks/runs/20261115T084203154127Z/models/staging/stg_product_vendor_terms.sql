-- Generated AutomateDV staging model for the raw-vault constructs on 'product_vendor_terms'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_vendor_terms_via_product'
derived_columns:
  VENDOR_BUSINESSENTITYID: 'BUSINESSENTITYID'
  AVERAGELEADTIME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(AVERAGELEADTIME AS text)), ''''), ''UTF8''), ''hex'')'
  STANDARDPRICE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STANDARDPRICE AS text)), ''''), ''UTF8''), ''hex'')'
  MINORDERQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MINORDERQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MAXORDERQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MAXORDERQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
null_columns:
  optional:
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
hashed_columns:
  LINK_PRODUCT_VENDOR_HK:
    - 'PRODUCTNUMBER'
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
  PRODUCT_VENDOR_TERMS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'AVERAGELEADTIME__CS'
      - 'STANDARDPRICE__CS'
      - 'MINORDERQTY__CS'
      - 'MAXORDERQTY__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
