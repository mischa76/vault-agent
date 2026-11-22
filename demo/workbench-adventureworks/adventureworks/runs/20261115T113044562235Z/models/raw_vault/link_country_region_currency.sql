{{ config(materialized='incremental') }}

{%- set source_model = "stg_country_region_currency" -%}
{%- set src_pk = "LINK_COUNTRY_REGION_CURRENCY_HK" -%}
{%- set src_fk = ["COUNTRYREGION_HK", "CURRENCY_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
