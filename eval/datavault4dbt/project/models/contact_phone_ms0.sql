{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_contact_h
src_hashdiff: hd_contact_phone_s
src_ma_key: phonetype
src_payload:
  - phonenumber
source_model: stg_phone
{%- endset -%}
{{ datavault4dbt.ma_sat_v0(yaml_metadata=yaml_metadata) }}
