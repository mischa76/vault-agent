-- Generated AutomateDV staging model for the raw-vault constructs on 'product_vendor_running_values'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_vendor_running_values_via_product'
derived_columns:
  VENDOR_BUSINESSENTITYID: 'BUSINESSENTITYID'
  LASTRECEIPTCOST__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LASTRECEIPTCOST AS text)), ''''), ''UTF8''), ''hex'')'
  LASTRECEIPTDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(LASTRECEIPTDATE AS text)), ''''), ''UTF8''), ''hex'')'
  ONORDERQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ONORDERQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
null_columns:
  optional:
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
hashed_columns:
  LINK_PRODUCT_VENDOR_HK:
    - 'PRODUCTNUMBER'
    - 'VENDOR_BUSINESSENTITYID'
    - 'UNITMEASURECODE'
  PRODUCT_VENDOR_RUNNING_VALUES_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'LASTRECEIPTCOST__CS'
      - 'LASTRECEIPTDATE__CS'
      - 'ONORDERQTY__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
