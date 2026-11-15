-- Generated AutomateDV staging model for the raw-vault constructs on 'special_offer_product'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_special_offer_product_via_product'
null_columns:
  optional:
    - 'SPECIALOFFERID'
    - 'PRODUCTNUMBER'
hashed_columns:
  SPECIALOFFER_HK: 'SPECIALOFFERID'
  PRODUCT_HK: 'PRODUCTNUMBER'
  LINK_SPECIAL_OFFER_PRODUCT_HK:
    - 'SPECIALOFFERID'
    - 'PRODUCTNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
