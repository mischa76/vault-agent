{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_contact_h
src_hashdiff: hd_contact_s
src_payload:
  - segment
source_model: stg_contact

{%- endset -%}
{{ datavault4dbt.sat_v0(yaml_metadata=yaml_metadata) }}
