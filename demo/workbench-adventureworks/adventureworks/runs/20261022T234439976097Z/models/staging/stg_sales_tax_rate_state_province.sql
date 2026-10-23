-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_tax_rate_state_province'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesTaxRate'
null_columns:
  optional:
    - 'STATEPROVINCEID'
    - 'TAXTYPE'
hashed_columns:
  SALESTAXRATE_HK:
    - 'STATEPROVINCEID'
    - 'TAXTYPE'
  STATEPROVINCE_HK: 'STATEPROVINCEID'
  LINK_SALES_TAX_RATE_STATE_PROVINCE_HK:
    - 'STATEPROVINCEID'
    - 'TAXTYPE'
    - 'STATEPROVINCEID'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
