{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_tax_rate_state_province" -%}
{%- set src_pk = "LINK_SALES_TAX_RATE_STATE_PROVINCE_HK" -%}
{%- set src_fk = ["SALESTAXRATE_HK", "STATEPROVINCE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
