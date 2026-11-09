{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_customer_h
business_keys:
  - customerid
source_models: stg_customer
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
