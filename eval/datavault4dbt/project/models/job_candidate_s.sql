{{ config(materialized='view') }}
{%- set yaml_metadata -%}
sat_v0: job_candidate_s0
hashkey: hk_job_candidate_h
hashdiff: hd_job_candidate_s
add_is_current_flag: true
{%- endset -%}
{{ datavault4dbt.sat_v1(yaml_metadata=yaml_metadata) }}
