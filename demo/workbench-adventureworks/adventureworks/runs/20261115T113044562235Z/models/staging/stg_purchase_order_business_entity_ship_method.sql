-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_business_entity_ship_method'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_purchase_order_business_entity_ship_method_via_shipmethod'
derived_columns:
  VENDOR_BUSINESSENTITYID: 'VENDORID'
  EMPLOYEE_BUSINESSENTITYID: 'EMPLOYEEID'
null_columns:
  optional:
    - 'PURCHASEORDERID'
    - 'VENDOR_BUSINESSENTITYID'
    - 'EMPLOYEE_BUSINESSENTITYID'
    - 'NAME'
hashed_columns:
  PURCHASEORDERHEADER_HK: 'PURCHASEORDERID'
  VENDOR_BUSINESSENTITY_HK: 'VENDOR_BUSINESSENTITYID'
  EMPLOYEE_BUSINESSENTITY_HK: 'EMPLOYEE_BUSINESSENTITYID'
  SHIPMETHOD_HK: 'NAME'
  LINK_PURCHASE_ORDER_BUSINESS_ENTITY_SHIP_METHOD_HK:
    - 'PURCHASEORDERID'
    - 'VENDOR_BUSINESSENTITYID'
    - 'EMPLOYEE_BUSINESSENTITYID'
    - 'NAME'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
