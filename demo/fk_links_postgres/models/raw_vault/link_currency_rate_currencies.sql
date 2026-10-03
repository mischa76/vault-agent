{{ config(materialized='incremental') }}

{%- set source_model = "stg_currency_rate_currencies" -%}
{%- set src_pk = "LINK_CURRENCY_RATE_CURRENCIES_HK" -%}
{%- set src_fk = ["CURRENCYRATE_HK", "FROM_CURRENCY_HK", "TO_CURRENCY_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
