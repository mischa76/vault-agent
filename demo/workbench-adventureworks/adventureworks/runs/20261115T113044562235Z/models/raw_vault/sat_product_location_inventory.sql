{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_location_inventory" -%}
{%- set src_pk = "LINK_PRODUCT_LOCATION_HK" -%}
{%- set src_cdk = ["SHELF", "BIN"] -%}
{%- set src_hashdiff = "PRODUCT_LOCATION_INVENTORY_HASHDIFF" -%}
{%- set src_payload = ["QUANTITY", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, src_hashdiff=src_hashdiff,
                      src_payload=src_payload, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
