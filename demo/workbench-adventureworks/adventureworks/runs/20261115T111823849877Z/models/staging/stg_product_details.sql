-- Generated AutomateDV staging model for the raw-vault constructs on 'product_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Product'
derived_columns:
  NAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(NAME AS text)), ''''), ''UTF8''), ''hex'')'
  MAKEFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MAKEFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  FINISHEDGOODSFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(FINISHEDGOODSFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  COLOR__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COLOR AS text)), ''''), ''UTF8''), ''hex'')'
  SIZE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SIZE AS text)), ''''), ''UTF8''), ''hex'')'
  WEIGHT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(WEIGHT AS text)), ''''), ''UTF8''), ''hex'')'
  DAYSTOMANUFACTURE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DAYSTOMANUFACTURE AS text)), ''''), ''UTF8''), ''hex'')'
  PRODUCTLINE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PRODUCTLINE AS text)), ''''), ''UTF8''), ''hex'')'
  CLASS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CLASS AS text)), ''''), ''UTF8''), ''hex'')'
  STYLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STYLE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  PRODUCT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'NAME__CS'
      - 'MAKEFLAG__CS'
      - 'FINISHEDGOODSFLAG__CS'
      - 'COLOR__CS'
      - 'SIZE__CS'
      - 'WEIGHT__CS'
      - 'DAYSTOMANUFACTURE__CS'
      - 'PRODUCTLINE__CS'
      - 'CLASS__CS'
      - 'STYLE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
