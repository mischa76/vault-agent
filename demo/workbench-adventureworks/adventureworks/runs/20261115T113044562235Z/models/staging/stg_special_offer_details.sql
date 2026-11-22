-- Generated AutomateDV staging model for the raw-vault constructs on 'special_offer_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SpecialOffer'
derived_columns:
  DESCRIPTION__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DESCRIPTION AS text)), ''''), ''UTF8''), ''hex'')'
  TYPE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TYPE AS text)), ''''), ''UTF8''), ''hex'')'
  CATEGORY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CATEGORY AS text)), ''''), ''UTF8''), ''hex'')'
  MINQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MINQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MAXQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MAXQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SPECIALOFFER_HK: 'SPECIALOFFERID'
  SPECIAL_OFFER_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DESCRIPTION__CS'
      - 'TYPE__CS'
      - 'CATEGORY__CS'
      - 'MINQTY__CS'
      - 'MAXQTY__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
