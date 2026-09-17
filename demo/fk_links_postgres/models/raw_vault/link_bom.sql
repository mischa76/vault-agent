{{ config(materialized='incremental') }}

{%- set source_model = "stg_bom" -%}
{%- set src_pk = "LINK_BOM_HK" -%}
{%- set src_fk = ["ASSEMBLY_PRODUCT_HK", "COMPONENT_PRODUCT_HK", "UNITMEASURE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
