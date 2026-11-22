-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_references'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderHeader'
derived_columns:
  PURCHASEORDERNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PURCHASEORDERNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  ACCOUNTNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACCOUNTNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  COMMENT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COMMENT AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SALES_ORDER_REFERENCES_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'PURCHASEORDERNUMBER__CS'
      - 'ACCOUNTNUMBER__CS'
      - 'COMMENT__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
