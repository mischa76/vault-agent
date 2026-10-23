{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_person_territory_history" -%}
{%- set src_pk = "LINK_SALES_PERSON_TERRITORY_HISTORY_HK" -%}
{%- set src_fk = ["SALES_PERSON_BUSINESSENTITY_HK", "SALESTERRITORY_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
