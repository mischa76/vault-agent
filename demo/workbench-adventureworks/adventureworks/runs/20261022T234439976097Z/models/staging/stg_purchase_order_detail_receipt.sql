-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_detail_receipt'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'PurchaseOrderDetail'
hashed_columns:
  PURCHASEORDERDETAIL_HK:
    - 'PURCHASEORDERID'
    - 'PURCHASEORDERDETAILID'
  PURCHASE_ORDER_DETAIL_RECEIPT_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'RECEIVEDQTY'
      - 'REJECTEDQTY'
      - 'STOCKEDQTY'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
