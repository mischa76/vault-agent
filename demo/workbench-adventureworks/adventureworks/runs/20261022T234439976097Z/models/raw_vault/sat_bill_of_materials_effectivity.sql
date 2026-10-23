{{ config(materialized='incremental', is_auto_end_dating=true) }}

{%- set source_model = "stg_bill_of_materials" -%}
{%- set src_pk = "LINK_BILL_OF_MATERIALS_HK" -%}
{%- set src_dfk = ["ASSEMBLY_PRODUCT_HK", "COMPONENT_PRODUCT_HK"] -%}
{%- set src_sfk = ["UNITMEASURE_HK"] -%}
{%- set src_start_date = "STARTDATE" -%}
{%- set src_end_date = "ENDDATE" -%}
{%- set src_eff = "APPLIED_DTS" -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.eff_sat(src_pk=src_pk, src_dfk=src_dfk, src_sfk=src_sfk,
                       src_start_date=src_start_date, src_end_date=src_end_date,
                       src_eff=src_eff, src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
