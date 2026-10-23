{{ config(materialized='incremental') }}

{%- set source_model = "stg_work_order_operation_details" -%}
{%- set src_pk = "WORKORDERROUTING_HK" -%}
{%- set src_cdk = ["PRODUCTID"] -%}
{%- set src_hashdiff = "WORK_ORDER_OPERATION_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["SCHEDULEDSTARTDATE", "SCHEDULEDENDDATE", "ACTUALSTARTDATE", "ACTUALENDDATE", "ACTUALRESOURCEHRS", "PLANNEDCOST", "ACTUALCOST", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, src_hashdiff=src_hashdiff,
                      src_payload=src_payload, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
