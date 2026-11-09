{{ config(materialized='view') }}
{%- set yaml_metadata -%}
sat_v0: contact_phone_ms0
hashkey: hk_contact_h
hashdiff: hd_contact_phone_s
ma_attribute: phonetype
add_is_current_flag: true
{%- endset -%}
{{ datavault4dbt.ma_sat_v1(yaml_metadata=yaml_metadata) }}
