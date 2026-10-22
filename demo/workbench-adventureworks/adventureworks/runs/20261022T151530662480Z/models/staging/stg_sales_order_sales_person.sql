-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_order_sales_person'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesOrderHeader'
derived_columns:
  SALES_PERSON_BUSINESSENTITYID: 'SALESPERSONID'
hashed_columns:
  SALESORDERHEADER_HK: 'SALESORDERNUMBER'
  SALES_PERSON_BUSINESSENTITY_HK: 'SALES_PERSON_BUSINESSENTITYID'
  LINK_SALES_ORDER_SALES_PERSON_HK:
    - 'SALESORDERNUMBER'
    - 'SALES_PERSON_BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
