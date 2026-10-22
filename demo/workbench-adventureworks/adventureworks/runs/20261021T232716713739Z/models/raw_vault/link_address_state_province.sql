{{ config(materialized='incremental') }}

{%- set source_model = "stg_address_state_province" -%}
{%- set src_pk = "LINK_ADDRESS_STATE_PROVINCE_HK" -%}
{%- set src_fk = ["ADDRESS_HK", "STATEPROVINCE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
