{{ config(materialized='incremental') }}

{%- set source_model = "stg_work_order_scrap_reason" -%}
{%- set src_pk = "LINK_WORK_ORDER_SCRAP_REASON_HK" -%}
{%- set src_fk = ["WORKORDER_HK", "SCRAPREASON_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
