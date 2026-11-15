-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_3: 'Vendor'
derived_columns:
  ACCOUNTNUMBER__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACCOUNTNUMBER AS text)), ''''), ''UTF8''), ''hex'')'
  NAME__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(NAME AS text)), ''''), ''UTF8''), ''hex'')'
  PURCHASINGWEBSERVICEURL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PURCHASINGWEBSERVICEURL AS text)), ''''), ''UTF8''), ''hex'')'
  CREDITRATING__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(CREDITRATING AS text)), ''''), ''UTF8''), ''hex'')'
  PREFERREDVENDORSTATUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PREFERREDVENDORSTATUS AS text)), ''''), ''UTF8''), ''hex'')'
  ACTIVEFLAG__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ACTIVEFLAG AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  BUSINESS_ENTITY_VENDOR_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'ACCOUNTNUMBER__CS'
      - 'NAME__CS'
      - 'PURCHASINGWEBSERVICEURL__CS'
  BUSINESS_ENTITY_VENDOR_STATUS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CREDITRATING__CS'
      - 'PREFERREDVENDORSTATUS__CS'
      - 'ACTIVEFLAG__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
