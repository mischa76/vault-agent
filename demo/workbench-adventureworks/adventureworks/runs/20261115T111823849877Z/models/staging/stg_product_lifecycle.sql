-- Generated AutomateDV staging model for the raw-vault constructs on 'product_lifecycle'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Product'
derived_columns:
  SELLSTARTDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SELLSTARTDATE AS text)), ''''), ''UTF8''), ''hex'')'
  SELLENDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SELLENDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  DISCONTINUEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DISCONTINUEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  PRODUCT_LIFECYCLE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SELLSTARTDATE__CS'
      - 'SELLENDDATE__CS'
      - 'DISCONTINUEDDATE__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
