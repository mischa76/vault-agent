{{ config(materialized='incremental') }}
{%- set yaml_metadata -%}
hashkey: hk_job_candidate_h
business_keys:
  - jobcandidateid
source_models: stg_job_candidate
{%- endset -%}
{{ datavault4dbt.hub(yaml_metadata=yaml_metadata) }}
