{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_order_sales_reason" -%}
{%- set src_pk = "LINK_SALES_ORDER_SALES_REASON_HK" -%}
{%- set src_fk = ["SALESORDERHEADER_HK", "SALESREASON_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
