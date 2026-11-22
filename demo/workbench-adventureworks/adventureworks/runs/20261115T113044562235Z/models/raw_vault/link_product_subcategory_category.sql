{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_subcategory_category" -%}
{%- set src_pk = "LINK_PRODUCT_SUBCATEGORY_CATEGORY_HK" -%}
{%- set src_fk = ["PRODUCTSUBCATEGORY_HK", "PRODUCTCATEGORY_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
