-- Generated AutomateDV staging model for the raw-vault constructs on 'product_inventory_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_inventory_details_via_product_and_location'
hashed_columns:
  LINK_PRODUCT_INVENTORY_HK:
    - 'PRODUCTNUMBER'
    - 'NAME'
  PRODUCT_INVENTORY_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'QUANTITY'
      - 'SHELF'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
