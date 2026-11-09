{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_order_day_h
business_keys:
  - orderdate
source_models: stg_order_line
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
