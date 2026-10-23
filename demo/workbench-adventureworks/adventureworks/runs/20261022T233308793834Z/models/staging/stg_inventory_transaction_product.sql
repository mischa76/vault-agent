-- Generated AutomateDV staging model for the raw-vault constructs on 'inventory_transaction_product'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'TransactionHistory'
null_columns:
  optional:
    - 'TRANSACTIONID'
    - 'PRODUCTID'
hashed_columns:
  TRANSACTIONHISTORY_HK: 'TRANSACTIONID'
  PRODUCT_HK: 'PRODUCTID'
  LINK_INVENTORY_TRANSACTION_PRODUCT_HK:
    - 'TRANSACTIONID'
    - 'PRODUCTID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
