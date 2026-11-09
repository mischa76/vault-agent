{{ config(materialized='view') }}
{%- set yaml_metadata -%}
sat_v0: customer_s0
hashkey: hk_customer_h
hashdiff: hd_customer_s
{%- endset -%}
{{ datavault4dbt.sat_v1(yaml_metadata=yaml_metadata) }}
