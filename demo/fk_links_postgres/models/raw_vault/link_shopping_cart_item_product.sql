{{ config(materialized='incremental') }}

{%- set source_model = "stg_shopping_cart_item_product" -%}
{%- set src_pk = "LINK_SHOPPING_CART_ITEM_PRODUCT_HK" -%}
{%- set src_fk = ["SHOPPINGCARTITEM_HK", "PRODUCT_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
