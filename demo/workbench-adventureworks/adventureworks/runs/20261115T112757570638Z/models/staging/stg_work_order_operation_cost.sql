-- Generated AutomateDV staging model for the raw-vault constructs on 'work_order_operation_cost'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'WorkOrderRouting'
derived_columns:
  ACTUALRESOURCEHRS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALRESOURCEHRS AS text)), ''''), ''UTF8''), ''hex'')'
  PLANNEDCOST__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PLANNEDCOST AS text)), ''''), ''UTF8''), ''hex'')'
  ACTUALCOST__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALCOST AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  WORKORDERROUTING_HK:
    - 'WORKORDERID'
    - 'OPERATIONSEQUENCE'
  WORK_ORDER_OPERATION_COST_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ACTUALRESOURCEHRS__CS'
      - 'PLANNEDCOST__CS'
      - 'ACTUALCOST__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
