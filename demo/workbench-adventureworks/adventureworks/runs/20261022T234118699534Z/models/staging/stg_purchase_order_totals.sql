-- Generated AutomateDV staging model for the raw-vault constructs on 'purchase_order_totals'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'PurchaseOrderHeader'
hashed_columns:
  PURCHASEORDERHEADER_HK: 'PURCHASEORDERID'
  PURCHASE_ORDER_TOTALS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SUBTOTAL'
      - 'TAXAMT'
      - 'FREIGHT'
      - 'TOTALDUE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
