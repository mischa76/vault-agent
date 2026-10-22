{{ config(materialized='incremental') }}

{%- set source_model = "stg_work_order_product_location_operation" -%}
{%- set src_pk = "LINK_WORK_ORDER_PRODUCT_LOCATION_HK" -%}
{%- set src_cdk = ["OPERATIONSEQUENCE"] -%}
{%- set src_hashdiff = "WORK_ORDER_PRODUCT_LOCATION_OPERATION_HASHDIFF" -%}
{%- set src_payload = ["SCHEDULEDSTARTDATE", "SCHEDULEDENDDATE", "ACTUALSTARTDATE", "ACTUALENDDATE", "ACTUALRESOURCEHRS", "PLANNEDCOST", "ACTUALCOST", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, src_hashdiff=src_hashdiff,
                      src_payload=src_payload, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
