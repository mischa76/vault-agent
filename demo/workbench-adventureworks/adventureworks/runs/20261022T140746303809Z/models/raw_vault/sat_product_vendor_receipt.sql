{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_vendor_receipt" -%}
{%- set src_pk = "LINK_PRODUCT_VENDOR_HK" -%}
{%- set src_hashdiff = "PRODUCT_VENDOR_RECEIPT_HASHDIFF" -%}
{%- set src_payload = ["LASTRECEIPTCOST", "LASTRECEIPTDATE", "ONORDERQTY"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
