-- Defect 1 (C56): a reserved payload column. The stage escapes it (the escape vars are set in
-- dbt_project.yml); postgres__sat_v0 prints the payload unescaped: syntax error at or near "group".
{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_customer_h
src_hashdiff: hd_customer_s
src_payload:
  - group
source_model: stg_customer
{%- endset -%}
{{ datavault4dbt.sat_v0(yaml_metadata=yaml_metadata) }}
