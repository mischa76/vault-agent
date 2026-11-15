{{ config(materialized='incremental') }}

{%- set source_model = "stg_purchase_order_dates" -%}
{%- set src_pk = "PURCHASEORDERHEADER_HK" -%}
{%- set src_hashdiff = "PURCHASE_ORDER_DATES_HASHDIFF" -%}
{%- set src_payload = ["ORDERDATE", "SHIPDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
