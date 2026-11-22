-- Generated AutomateDV staging model for the raw-vault constructs on 'work_order_operation_schedule'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'WorkOrderRouting'
derived_columns:
  SCHEDULEDSTARTDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SCHEDULEDSTARTDATE AS text)), ''''), ''UTF8''), ''hex'')'
  SCHEDULEDENDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SCHEDULEDENDDATE AS text)), ''''), ''UTF8''), ''hex'')'
  ACTUALSTARTDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALSTARTDATE AS text)), ''''), ''UTF8''), ''hex'')'
  ACTUALENDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALENDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  WORKORDERROUTING_HK:
    - 'WORKORDERID'
    - 'OPERATIONSEQUENCE'
  WORK_ORDER_OPERATION_SCHEDULE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SCHEDULEDSTARTDATE__CS'
      - 'SCHEDULEDENDDATE__CS'
      - 'ACTUALSTARTDATE__CS'
      - 'ACTUALENDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
