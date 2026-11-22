{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_order_line_detail" -%}
{%- set src_pk = "LINK_SALES_ORDER_LINE_HK" -%}
{%- set src_hashdiff = "SALES_ORDER_LINE_DETAIL_HASHDIFF" -%}
{%- set src_payload = ["ORDERQTY"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
