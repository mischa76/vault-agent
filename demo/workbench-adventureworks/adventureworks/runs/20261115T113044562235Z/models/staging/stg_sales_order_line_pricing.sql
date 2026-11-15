-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_line_pricing'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderDetail'
derived_columns:
  ORDERQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ORDERQTY AS text)), ''''), ''UTF8''), ''hex'')'
  UNITPRICE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(UNITPRICE AS text)), ''''), ''UTF8''), ''hex'')'
  UNITPRICEDISCOUNT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(UNITPRICEDISCOUNT AS text)), ''''), ''UTF8''), ''hex'')'
  LINETOTAL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LINETOTAL AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SALESORDERDETAIL_HK:
    - 'SALESORDERID'
    - 'SALESORDERDETAILID'
  SALES_ORDER_LINE_PRICING_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ORDERQTY__CS'
      - 'UNITPRICE__CS'
      - 'UNITPRICEDISCOUNT__CS'
      - 'LINETOTAL__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
