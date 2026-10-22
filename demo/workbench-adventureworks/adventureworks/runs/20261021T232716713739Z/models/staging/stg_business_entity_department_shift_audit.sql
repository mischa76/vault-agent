-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity_department_shift_audit'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_2: 'EmployeeDepartmentHistory'
hashed_columns:
  LINK_BUSINESS_ENTITY_DEPARTMENT_SHIFT_HK:
    - 'BUSINESSENTITYID'
    - 'DEPARTMENTID'
    - 'SHIFTID'
  BUSINESS_ENTITY_DEPARTMENT_SHIFT_AUDIT_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
