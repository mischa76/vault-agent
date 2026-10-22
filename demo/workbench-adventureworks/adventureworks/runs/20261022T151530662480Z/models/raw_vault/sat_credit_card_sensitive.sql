{{ config(materialized='incremental') }}

{%- set source_model = "stg_credit_card_sensitive" -%}
{%- set src_pk = "CREDITCARD_HK" -%}
{%- set src_hashdiff = "CREDIT_CARD_SENSITIVE_HASHDIFF" -%}
{%- set src_payload = ["CARDNUMBER", "EXPMONTH", "EXPYEAR"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
