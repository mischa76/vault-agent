{{ config(materialized='incremental') }}

{%- set source_model = "stg_customer" -%}
{%- set src_pk = "CUSTOMER_HK" -%}
{%- set src_hashdiff = "CUSTOMER_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["CUSTOMER_NAME", "DATE_OF_BIRTH"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
