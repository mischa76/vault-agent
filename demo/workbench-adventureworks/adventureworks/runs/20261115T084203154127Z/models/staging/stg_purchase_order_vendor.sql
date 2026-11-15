-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_vendor'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'PurchaseOrderHeader'
derived_columns:
  VENDOR_BUSINESSENTITYID: 'VENDORID'
null_columns:
  optional:
    - 'PURCHASEORDERID'
    - 'VENDOR_BUSINESSENTITYID'
hashed_columns:
  PURCHASEORDERHEADER_HK: 'PURCHASEORDERID'
  VENDOR_BUSINESSENTITY_HK: 'VENDOR_BUSINESSENTITYID'
  LINK_PURCHASE_ORDER_VENDOR_HK:
    - 'PURCHASEORDERID'
    - 'VENDOR_BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
