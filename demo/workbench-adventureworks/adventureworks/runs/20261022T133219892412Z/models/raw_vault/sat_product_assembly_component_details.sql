{{ config(materialized='incremental') }}

{%- set source_model = "stg_product_assembly_component" -%}
{%- set src_pk = "LINK_PRODUCT_ASSEMBLY_COMPONENT_HK" -%}
{%- set src_hashdiff = "PRODUCT_ASSEMBLY_COMPONENT_DETAILS_HASHDIFF" -%}
{%- set src_payload = ["BOMLEVEL", "PERASSEMBLYQTY", "MODIFIEDDATE"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, src_payload=src_payload,
                   src_ldts=src_ldts, src_source=src_source, source_model=source_model) }}
