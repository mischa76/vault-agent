{{ config(materialized='view') }}
{%- set yaml_metadata -%}
sat_v0: contact_s0
hashkey: hk_contact_h
hashdiff: hd_contact_s
add_is_current_flag: true
{%- endset -%}
{{ datavault4dbt.sat_v1(yaml_metadata=yaml_metadata) }}
