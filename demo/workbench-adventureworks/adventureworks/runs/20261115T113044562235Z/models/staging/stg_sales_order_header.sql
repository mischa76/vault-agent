-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_header'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_sales_order_header_via_4_8f0389'
derived_columns:
  SALES_PERSON_BUSINESSENTITYID: 'SALESPERSONID'
  BILL_TO_ADDRESSID: 'BILLTOADDRESSID'
  SHIP_TO_ADDRESSID: 'SHIPTOADDRESSID'
null_columns:
  optional:
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'NAME'
    - 'BILL_TO_ADDRESSID'
    - 'SHIP_TO_ADDRESSID'
    - 'NAME_VIA_SHIPMETHOD'
    - 'CARDNUMBER'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  CUSTOMER_HK: 'ACCOUNTNUMBER_VIA_CUSTOMER'
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  SALESTERRITORY_HK: 'NAME'
  BILL_TO_ADDRESS_HK: 'BILL_TO_ADDRESSID'
  SHIP_TO_ADDRESS_HK: 'SHIP_TO_ADDRESSID'
  SHIPMETHOD_HK: 'NAME_VIA_SHIPMETHOD'
  CREDITCARD_HK: 'CARDNUMBER'
  LINK_SALES_ORDER_HEADER_HK:
    - 'SALESORDERNUMBER'
    - 'ACCOUNTNUMBER_VIA_CUSTOMER'
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'NAME'
    - 'BILL_TO_ADDRESSID'
    - 'SHIP_TO_ADDRESSID'
    - 'NAME_VIA_SHIPMETHOD'
    - 'CARDNUMBER'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
