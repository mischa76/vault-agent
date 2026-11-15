-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_line_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'PurchaseOrderDetail'
derived_columns:
  DUEDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DUEDATE AS text)), ''''), ''UTF8''), ''hex'')'
  ORDERQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ORDERQTY AS text)), ''''), ''UTF8''), ''hex'')'
  UNITPRICE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(UNITPRICE AS text)), ''''), ''UTF8''), ''hex'')'
  LINETOTAL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LINETOTAL AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PURCHASEORDERDETAIL_HK:
    - 'PURCHASEORDERID'
    - 'PURCHASEORDERDETAILID'
  PURCHASE_ORDER_LINE_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'DUEDATE__CS'
      - 'ORDERQTY__CS'
      - 'UNITPRICE__CS'
      - 'LINETOTAL__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
