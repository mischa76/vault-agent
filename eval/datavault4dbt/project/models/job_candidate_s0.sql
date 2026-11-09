{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
parent_hashkey: hk_job_candidate_h
src_hashdiff: hd_job_candidate_s
src_payload:
  - resume
  - modifieddate
source_model: stg_job_candidate
{%- endset -%}
{{ datavault4dbt.sat_v0(yaml_metadata=yaml_metadata) }}
