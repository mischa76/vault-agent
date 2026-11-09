{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_probe_h
business_keys:
  - probeid
source_models: stg_probe
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
