-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_job_candidate'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_2: 'JobCandidate'
hashed_columns:
  JOBCANDIDATE_HK: 'JOBCANDIDATEID'
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  LINK_BUSINESS_ENTITY_JOB_CANDIDATE_HK:
    - 'JOBCANDIDATEID'
    - 'BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
