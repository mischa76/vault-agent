-- Generated AutomateDV staging model for the raw-vault constructs on 'work_order_operation_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'WorkOrderRouting'
hashed_columns:
  WORKORDERROUTING_HK:
    - 'WORKORDERID'
    - 'OPERATIONSEQUENCE'
  WORK_ORDER_OPERATION_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SCHEDULEDSTARTDATE'
      - 'SCHEDULEDENDDATE'
      - 'ACTUALSTARTDATE'
      - 'ACTUALENDDATE'
      - 'ACTUALRESOURCEHRS'
      - 'PLANNEDCOST'
      - 'ACTUALCOST'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
