{{ config(materialized='incremental') }}

{%- set source_model = "stg_country_region_currency_details" -%}
{%- set src_pk = "LINK_COUNTRY_REGION_CURRENCY_HK" -%}
{%- set src_hashdiff = "COUNTRY_REGION_CURRENCY_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
