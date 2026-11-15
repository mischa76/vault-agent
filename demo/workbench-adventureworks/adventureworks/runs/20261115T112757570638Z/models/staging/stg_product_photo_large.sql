-- Generated AutomateDV staging model for the raw-vault constructs on 'product_photo_large'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'ProductPhoto'
derived_columns:
  LARGEPHOTO__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LARGEPHOTO AS text)), ''''), ''UTF8''), ''hex'')'
  LARGEPHOTOFILENAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LARGEPHOTOFILENAME AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCTPHOTO_HK: 'PRODUCTPHOTOID'
  PRODUCT_PHOTO_LARGE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'LARGEPHOTO__CS'
      - 'LARGEPHOTOFILENAME__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
