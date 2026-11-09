{{ config(materialized='view') }}
{%- set yaml_metadata -%}
sat_v0: probe_s0
hashkey: hk_probe_h
hashdiff: hd_probe_s
add_is_current_flag: true
{%- endset -%}
{{ datavault4dbt.sat_v1(yaml_metadata=yaml_metadata) }}
