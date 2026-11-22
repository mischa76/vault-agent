{{ config(materialized='incremental') }}

{%- set source_model = "stg_special_offer_validity" -%}
{%- set src_pk = "SPECIALOFFER_HK" -%}
{%- set src_hashdiff = "SPECIAL_OFFER_VALIDITY_HASHDIFF" -%}
{%- set src_payload = ["STARTDATE", "ENDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
