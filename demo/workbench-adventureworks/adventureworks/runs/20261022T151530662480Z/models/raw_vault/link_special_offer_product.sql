{{ config(materialized='incremental') }}

{%- set source_model = "stg_special_offer_product" -%}
{%- set src_pk = "LINK_SPECIAL_OFFER_PRODUCT_HK" -%}
{%- set src_fk = ["SPECIALOFFER_HK", "PRODUCT_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
