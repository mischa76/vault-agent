{{ config(materialized='incremental') }}

{%- set source_model = "stg_state_province_territory" -%}
{%- set src_pk = "STATEPROVINCE_HK" -%}
{%- set src_hashdiff = "STATE_PROVINCE_TERRITORY_HASHDIFF" -%}
{%- set src_payload = ["TERRITORYID"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
