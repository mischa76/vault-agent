{{ config(materialized='incremental') }}

{%- set source_model = "stg_contact_type" -%}
{%- set src_pk = "CONTACTTYPE_HK" -%}
{%- set src_hashdiff = "CONTACT_TYPE_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["NAME"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
