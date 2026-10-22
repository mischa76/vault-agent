{{ config(materialized='incremental', is_auto_end_dating=true) }}

{%- set source_model = "stg_business_entity_department_shift" -%}
{%- set src_pk = "LINK_BUSINESS_ENTITY_DEPARTMENT_SHIFT_HK" -%}
{%- set src_dfk = "BUSINESSENTITY_HK" -%}
{%- set src_sfk = ["DEPARTMENT_HK", "SHIFT_HK"] -%}
{%- set src_start_date = "STARTDATE" -%}
{%- set src_end_date = "ENDDATE" -%}
{%- set src_eff = "APPLIED_DTS" -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.eff_sat(src_pk=src_pk, src_dfk=src_dfk, src_sfk=src_sfk,
                       src_start_date=src_start_date, src_end_date=src_end_date,
                       src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
