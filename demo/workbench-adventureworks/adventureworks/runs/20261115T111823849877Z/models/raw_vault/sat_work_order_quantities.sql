{{ config(materialized='incremental') }}

{%- set source_model = "stg_work_order_quantities" -%}
{%- set src_pk = "WORKORDER_HK" -%}
{%- set src_hashdiff = "WORK_ORDER_QUANTITIES_HASHDIFF" -%}
{%- set src_payload = ["ORDERQTY", "STOCKEDQTY", "SCRAPPEDQTY"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
