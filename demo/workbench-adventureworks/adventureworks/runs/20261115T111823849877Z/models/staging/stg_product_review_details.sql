-- Generated AutomateDV staging model for the raw-vault constructs on 'product_review_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductReview'
derived_columns:
  REVIEWDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVIEWDATE AS text)), ''''), ''UTF8''), ''hex'')'
  RATING__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(RATING AS text)), ''''), ''UTF8''), ''hex'')'
  COMMENTS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COMMENTS AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCTREVIEW_HK: 'PRODUCTREVIEWID'
  PRODUCT_REVIEW_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'REVIEWDATE__CS'
      - 'RATING__CS'
      - 'COMMENTS__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
