{{ config(materialized='incremental') }}

{%- set source_model = "stg_business_entity_vendor" -%}
{%- set src_pk = "BUSINESSENTITY_HK" -%}
{%- set src_hashdiff = "BUSINESS_ENTITY_VENDOR_STATUS_HASHDIFF" -%}
{%- set src_payload = ["CREDITRATING", "PREFERREDVENDORSTATUS", "ACTIVEFLAG", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
