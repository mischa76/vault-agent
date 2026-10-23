{{ config(materialized='incremental') }}

{%- set source_model = ["stg_inventory_transaction_transactionhistory", "stg_inventory_transaction_transactionhistoryarchive"] -%}
{%- set src_pk = "TRANSACTIONHISTORY_HK" -%}
{%- set src_nk = "TRANSACTIONID" -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts,
                   src_source=src_source, source_model=source_model) }}
