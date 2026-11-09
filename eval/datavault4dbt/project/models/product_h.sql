{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_product_h
business_keys:
  - productnumber
source_models: stg_product
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
