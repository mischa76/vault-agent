{{ config(materialized='incremental') }}

{%- set source_model = "stg_business_entity_sales_territory" -%}
{%- set src_pk = "LINK_BUSINESS_ENTITY_SALES_TERRITORY_HK" -%}
{%- set src_fk = ["BUSINESSENTITY_HK", "SALESTERRITORY_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
