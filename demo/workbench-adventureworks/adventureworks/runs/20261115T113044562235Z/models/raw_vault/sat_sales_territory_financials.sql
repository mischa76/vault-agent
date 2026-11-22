{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_territory_financials" -%}
{%- set src_pk = "SALESTERRITORY_HK" -%}
{%- set src_hashdiff = "SALES_TERRITORY_FINANCIALS_HASHDIFF" -%}
{%- set src_payload = ["SALESYTD", "SALESLASTYEAR", "COSTYTD", "COSTLASTYEAR"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
