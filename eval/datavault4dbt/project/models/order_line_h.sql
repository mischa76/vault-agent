{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_order_line_h
business_keys:
  - orderlineid
source_models: stg_order_line
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
