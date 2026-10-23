-- Generated AutomateDV staging model for the raw-vault constructs on 'product_location_inventory'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'ProductInventory'
null_columns:
  optional:
    - 'PRODUCTID'
    - 'LOCATIONID'
hashed_columns:
  LINK_PRODUCT_LOCATION_HK:
    - 'PRODUCTID'
    - 'LOCATIONID'
  PRODUCT_LOCATION_INVENTORY_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'QUANTITY'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
