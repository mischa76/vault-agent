-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderHeader'
derived_columns:
  REVISIONNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(REVISIONNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  ORDERDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ORDERDATE AS text)), ''''), ''UTF8''), ''hex'')'
  DUEDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(DUEDATE AS text)), ''''), ''UTF8''), ''hex'')'
  SHIPDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SHIPDATE AS text)), ''''), ''UTF8''), ''hex'')'
  STATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(STATUS AS text)), ''''), ''UTF8''), ''hex'')'
  ONLINEORDERFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ONLINEORDERFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  PURCHASEORDERNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PURCHASEORDERNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  ACCOUNTNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACCOUNTNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  COMMENT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COMMENT AS text)), ''''), ''UTF8''), ''hex'')'
  ROWGUID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ROWGUID AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SALES_ORDER_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'REVISIONNUMBER__CS'
      - 'ORDERDATE__CS'
      - 'DUEDATE__CS'
      - 'SHIPDATE__CS'
      - 'STATUS__CS'
      - 'ONLINEORDERFLAG__CS'
      - 'PURCHASEORDERNUMBER__CS'
      - 'ACCOUNTNUMBER__CS'
      - 'COMMENT__CS'
      - 'ROWGUID__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
