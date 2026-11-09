{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_order_guid_h
business_keys:
  - rowguid
source_models: stg_order_line
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
