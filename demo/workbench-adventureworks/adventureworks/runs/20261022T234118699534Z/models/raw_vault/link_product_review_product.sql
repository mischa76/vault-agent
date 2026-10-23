{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_review_product" -%}
{%- set src_pk = "LINK_PRODUCT_REVIEW_PRODUCT_HK" -%}
{%- set src_fk = ["PRODUCTREVIEW_HK", "PRODUCT_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
