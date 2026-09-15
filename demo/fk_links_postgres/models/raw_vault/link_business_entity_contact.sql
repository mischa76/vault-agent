{{ config(materialized='incremental') }}

{%- set source_model = "stg_business_entity_contact" -%}
{%- set src_pk = "LINK_BUSINESS_ENTITY_CONTACT_HK" -%}
{%- set src_fk = ["ORGANISATION_BUSINESSENTITY_HK", "PERSON_HK", "CONTACTTYPE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
