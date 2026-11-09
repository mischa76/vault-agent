{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_probe_h
src_hashdiff: hd_probe_s
src_payload:
  - doc
  - pos
source_model: stg_probe
{%- endset -%}
{{ datavault4dbt.sat_v0(yaml_metadata=yaml_metadata) }}
