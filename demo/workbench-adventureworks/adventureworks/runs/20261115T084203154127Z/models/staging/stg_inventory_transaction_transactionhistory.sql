-- Generated AutomateDV staging model for the raw-vault constructs on 'inventory_transaction'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'TransactionHistory'
derived_columns:
  REFERENCEORDERID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REFERENCEORDERID AS text)), ''''), ''UTF8''), ''hex'')'
  REFERENCEORDERLINEID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REFERENCEORDERLINEID AS text)), ''''), ''UTF8''), ''hex'')'
  TRANSACTIONDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TRANSACTIONDATE AS text)), ''''), ''UTF8''), ''hex'')'
  TRANSACTIONTYPE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(TRANSACTIONTYPE AS text)), ''''), ''UTF8''), ''hex'')'
  QUANTITY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(QUANTITY AS text)), ''''), ''UTF8''), ''hex'')'
  ACTUALCOST__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTUALCOST AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  TRANSACTIONHISTORY_HK: 'TRANSACTIONID'
  INVENTORY_TRANSACTION_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'REFERENCEORDERID__CS'
      - 'REFERENCEORDERLINEID__CS'
      - 'TRANSACTIONDATE__CS'
      - 'TRANSACTIONTYPE__CS'
      - 'QUANTITY__CS'
      - 'ACTUALCOST__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
