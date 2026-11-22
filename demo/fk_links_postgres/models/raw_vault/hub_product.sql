{{ config(materialized='incremental') }}

{%- set source_model = "stg_product" -%}
{%- set src_pk = "PRODUCT_HK" -%}
{%- set src_nk = "PRODUCTNUMBER" -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts,
                   src_source=src_source, source_model=source_model) }}
