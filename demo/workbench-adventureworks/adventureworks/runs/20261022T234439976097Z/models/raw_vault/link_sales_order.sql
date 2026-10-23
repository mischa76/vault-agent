{{ config(materialized='incremental') }}

{%- set source_model = "stg_sales_order" -%}
{%- set src_pk = "LINK_SALES_ORDER_HK" -%}
{%- set src_fk = ["SALESORDERHEADER_HK", "CUSTOMER_HK", "SALES_PERSON_BUSINESSENTITY_HK", "SALESTERRITORY_HK", "BILL_TO_ADDRESS_HK", "SHIP_TO_ADDRESS_HK", "SHIPMETHOD_HK", "CREDITCARD_HK", "CURRENCYRATE_HK"] -%}
{%- set src_ldts = "LOAD_DATETIME" -%}
{%- set src_source = "RECORD_SOURCE" -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
