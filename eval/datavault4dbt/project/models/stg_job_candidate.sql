{%- set yaml_metadata -%}
source_model:
  hr: JobCandidate
ldts: load_datetime
rsrc: record_source
hashed_columns:
  hk_job_candidate_h:
    - jobcandidateid
  hd_job_candidate_s:
    is_hashdiff: true
    columns:
      - resume
      - modifieddate
{%- endset -%}
{{ datavault4dbt.stage(yaml_metadata=yaml_metadata) }}
