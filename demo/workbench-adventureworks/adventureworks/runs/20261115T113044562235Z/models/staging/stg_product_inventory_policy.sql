-- Generated AutomateDV staging model for the raw-vault constructs on 'product_inventory_policy'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'Product'
derived_columns:
  SAFETYSTOCKLEVEL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SAFETYSTOCKLEVEL AS text)), ''''), ''UTF8''), ''hex'')'
  REORDERPOINT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REORDERPOINT AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PRODUCT_HK: 'PRODUCTNUMBER'
  PRODUCT_INVENTORY_POLICY_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SAFETYSTOCKLEVEL__CS'
      - 'REORDERPOINT__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
