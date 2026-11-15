{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_territory_country_region" -%}
{%- set src_pk = "LINK_SALES_TERRITORY_COUNTRY_REGION_HK" -%}
{%- set src_fk = ["SALESTERRITORY_HK", "COUNTRYREGION_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
