-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_2: 'Employee'
derived_columns:
  NATIONALIDNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(NATIONALIDNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  LOGINID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LOGINID AS text)), ''''), ''UTF8''), ''hex'')'
  JOBTITLE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(JOBTITLE AS text)), ''''), ''UTF8''), ''hex'')'
  HIREDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(HIREDATE AS text)), ''''), ''UTF8''), ''hex'')'
  SALARIEDFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALARIEDFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  CURRENTFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CURRENTFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  BIRTHDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(BIRTHDATE AS text)), ''''), ''UTF8''), ''hex'')'
  GENDER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(GENDER AS text)), ''''), ''UTF8''), ''hex'')'
  MARITALSTATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MARITALSTATUS AS text)), ''''), ''UTF8''), ''hex'')'
  VACATIONHOURS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(VACATIONHOURS AS text)), ''''), ''UTF8''), ''hex'')'
  SICKLEAVEHOURS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SICKLEAVEHOURS AS text)), ''''), ''UTF8''), ''hex'')'
  ORGANIZATIONNODE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ORGANIZATIONNODE AS text)), ''''), ''UTF8''), ''hex'')'
  ORGANIZATIONLEVEL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ORGANIZATIONLEVEL AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  BUSINESS_ENTITY_EMPLOYEE_IDENTIFIERS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'NATIONALIDNUMBER__CS'
      - 'LOGINID__CS'
  BUSINESS_ENTITY_EMPLOYEE_JOB_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'JOBTITLE__CS'
      - 'HIREDATE__CS'
      - 'SALARIEDFLAG__CS'
      - 'CURRENTFLAG__CS'
      - 'MODIFIEDDATE__CS'
  BUSINESS_ENTITY_EMPLOYEE_PERSONAL_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'BIRTHDATE__CS'
      - 'GENDER__CS'
      - 'MARITALSTATUS__CS'
  BUSINESS_ENTITY_EMPLOYEE_LEAVE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'VACATIONHOURS__CS'
      - 'SICKLEAVEHOURS__CS'
  BUSINESS_ENTITY_EMPLOYEE_HIERARCHY_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ORGANIZATIONNODE__CS'
      - 'ORGANIZATIONLEVEL__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
