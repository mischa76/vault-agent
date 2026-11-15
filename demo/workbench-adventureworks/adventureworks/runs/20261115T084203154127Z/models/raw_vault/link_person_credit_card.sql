{{ config(materialized='incremental') }}

{%- set source_model = "stg_person_credit_card" -%}
{%- set src_pk = "LINK_PERSON_CREDIT_CARD_HK" -%}
{%- set src_fk = ["PERSON_BUSINESSENTITY_HK", "CREDITCARD_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
