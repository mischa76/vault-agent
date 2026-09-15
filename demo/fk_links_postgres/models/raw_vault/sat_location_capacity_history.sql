{{ config(materialized='incremental') }}

{%- set source_model = "stg_location_capacity_history" -%}
{%- set src_pk = "LOCATION_HK" -%}
{%- set src_cdk = ["STARTDATE"] -%}
{%- set src_hashdiff = "LOCATION_CAPACITY_HISTORY_HASHDIFF" -%}
{%- set src_payload = ["COSTRATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, src_hashdiff=src_hashdiff,
                      src_payload=src_payload, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
