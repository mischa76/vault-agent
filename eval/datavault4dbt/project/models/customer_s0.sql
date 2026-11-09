{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_customer_h
src_hashdiff: hd_customer_s
src_payload:
  - segment
source_model: stg_customer
{%- endset -%}
{{ datavault4dbt.sat_v0(yaml_metadata=yaml_metadata) }}
