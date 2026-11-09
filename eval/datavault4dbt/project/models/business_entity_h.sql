{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_business_entity_h
business_keys:
  - businessentityid
source_models: stg_business_entity
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
