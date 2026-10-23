{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_unit_measure" -%}
{%- set src_pk = "LINK_PRODUCT_UNIT_MEASURE_HK" -%}
{%- set src_fk = ["PRODUCT_HK", "SIZE_UNITMEASURE_HK", "WEIGHT_UNITMEASURE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
