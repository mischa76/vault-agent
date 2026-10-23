-- Generated AutomateDV staging model for the raw-vault constructs on 'customer_store'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'Customer'
derived_columns:
  STORE_BUSINESSENTITYID: 'STOREID'
null_columns:
  optional:
    - 'STORE_BUSINESSENTITYID'
hashed_columns:
  CUSTOMER_HK: 'ACCOUNTNUMBER'
  STORE_BUSINESSENTITY_HK: 'STORE_BUSINESSENTITYID'
  LINK_CUSTOMER_STORE_HK:
    - 'ACCOUNTNUMBER'
    - 'STORE_BUSINESSENTITYID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
