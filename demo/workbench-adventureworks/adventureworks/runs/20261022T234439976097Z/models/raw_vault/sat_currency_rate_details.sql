{{ config(materialized='incremental') }}

{%- set source_model = "stg_currency_rate_details" -%}
{%- set src_pk = "CURRENCYRATE_HK" -%}
{%- set src_hashdiff = "CURRENCY_RATE_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["AVERAGERATE", "ENDOFDAYRATE", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
