{{ config(materialized='incremental') }}

{%- set source_model = "stg_transfer" -%}
{%- set src_pk = "LINK_TRANSFER_HK" -%}
{%- set src_fk = ["ACCOUNT_HK", "COUNTERPARTY_ACCOUNT_HK"] -%}
{%- set src_payload = ["AMOUNT", "CURRENCY"] -%}
{%- set src_eff = "TRANSFER_TIMESTAMP" -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.t_link(src_pk=src_pk, src_fk=src_fk, src_payload=src_payload,
                      src_extra_columns=none,
                      src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
