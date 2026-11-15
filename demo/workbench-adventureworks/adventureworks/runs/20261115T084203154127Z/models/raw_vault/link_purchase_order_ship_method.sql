{{ config(materialized='incremental') }}

{%- set source_model = "stg_purchase_order_ship_method" -%}
{%- set src_pk = "LINK_PURCHASE_ORDER_SHIP_METHOD_HK" -%}
{%- set src_fk = ["PURCHASEORDERHEADER_HK", "SHIPMETHOD_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
