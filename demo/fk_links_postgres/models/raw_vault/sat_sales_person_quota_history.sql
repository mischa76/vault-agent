{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_person_quota_history" -%}
{%- set src_pk = "EMPLOYEE_HK" -%}
{%- set src_cdk = ["QUOTADATE"] -%}
{%- set src_hashdiff = "SALES_PERSON_QUOTA_HISTORY_HASHDIFF" -%}
{%- set src_payload = ["SALESQUOTA"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, src_hashdiff=src_hashdiff,
                      src_payload=src_payload, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
