-- Generated AutomateDV staging model for the raw-vault constructs on 'business_entity'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesPerson'
derived_columns:
  SALESQUOTA__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALESQUOTA AS text)), ''''), ''UTF8''), ''hex'')'
  BONUS__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(BONUS AS text)), ''''), ''UTF8''), ''hex'')'
  COMMISSIONPCT__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COMMISSIONPCT AS text)), ''''), ''UTF8''), ''hex'')'
  SALESYTD__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALESYTD AS text)), ''''), ''UTF8''), ''hex'')'
  SALESLASTYEAR__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALESLASTYEAR AS text)), ''''), ''UTF8''), ''hex'')'
  ROWGUID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ROWGUID AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  BUSINESSENTITY_HK: 'BUSINESSENTITYID'
  BUSINESS_ENTITY_SALES_PERSON_COMPENSATION_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SALESQUOTA__CS'
      - 'BONUS__CS'
      - 'COMMISSIONPCT__CS'
  BUSINESS_ENTITY_SALES_PERSON_PERFORMANCE_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SALESYTD__CS'
      - 'SALESLASTYEAR__CS'
      - 'ROWGUID__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
