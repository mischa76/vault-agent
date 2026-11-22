-- Generated AutomateDV staging model for the raw-vault constructs on 'product_review_reviewer_pii'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'ProductReview'
derived_columns:
  REVIEWERNAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVIEWERNAME AS text)), ''''), ''UTF8''), ''hex'')'
  EMAILADDRESS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(EMAILADDRESS AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCTREVIEW_HK: 'PRODUCTREVIEWID'
  PRODUCT_REVIEW_REVIEWER_PII_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'REVIEWERNAME__CS'
      - 'EMAILADDRESS__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
