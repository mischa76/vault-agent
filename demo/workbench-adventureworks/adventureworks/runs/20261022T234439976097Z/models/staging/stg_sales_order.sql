-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: inferred — see review queue).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  inferred: 'raw_sales_order'
derived_columns:
  SALES_PERSON_BUSINESSENTITYID: 'SALESPERSONID'
  BILL_TO_ADDRESSID: 'BILLTOADDRESSID'
  SHIP_TO_ADDRESSID: 'SHIPTOADDRESSID'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  CUSTOMER_HK: 'ACCOUNTNUMBER'
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  SALESTERRITORY_HK: 'TERRITORYID'
  BILL_TO_ADDRESS_HK: 'BILL_TO_ADDRESSID'
  SHIP_TO_ADDRESS_HK: 'SHIP_TO_ADDRESSID'
  SHIPMETHOD_HK: 'SHIPMETHODID'
  CREDITCARD_HK: 'CREDITCARDID'
  CURRENCYRATE_HK:
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
  LINK_SALES_ORDER_HK:
    - 'SALESORDERNUMBER'
    - 'ACCOUNTNUMBER'
    - 'SALES_PERSON_BUSINESSENTITYID'
    - 'TERRITORYID'
    - 'BILL_TO_ADDRESSID'
    - 'SHIP_TO_ADDRESSID'
    - 'SHIPMETHODID'
    - 'CREDITCARDID'
    - 'CURRENCYRATEDATE'
    - 'FROMCURRENCYCODE'
    - 'TOCURRENCYCODE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
