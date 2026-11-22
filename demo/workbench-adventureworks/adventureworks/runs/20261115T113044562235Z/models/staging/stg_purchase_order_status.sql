-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_status'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'PurchaseOrderHeader'
derived_columns:
  STATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STATUS AS text)), ''''), ''UTF8''), ''hex'')'
  REVISIONNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVISIONNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  PURCHASEORDERHEADER_HK: 'PURCHASEORDERID'
  PURCHASE_ORDER_STATUS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'STATUS__CS'
      - 'REVISIONNUMBER__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
