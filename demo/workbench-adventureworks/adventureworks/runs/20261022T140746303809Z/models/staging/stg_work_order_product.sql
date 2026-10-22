-- Generated AutomateDV staging model for the raw-vault constructs on 'work_order_product'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'WorkOrder'
hashed_columns:
  WORKORDER_HK: 'WORKORDERID'
  PRODUCT_HK: 'PRODUCTID'
  LINK_WORK_ORDER_PRODUCT_HK:
    - 'WORKORDERID'
    - 'PRODUCTID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
