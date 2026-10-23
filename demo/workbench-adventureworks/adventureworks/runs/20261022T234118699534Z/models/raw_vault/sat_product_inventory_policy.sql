{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_inventory_policy" -%}
{%- set src_pk = "PRODUCT_HK" -%}
{%- set src_hashdiff = "PRODUCT_INVENTORY_POLICY_HASHDIFF" -%}
{%- set src_payload = ["SAFETYSTOCKLEVEL", "REORDERPOINT"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
