-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_territory_financials'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'SalesTerritory'
derived_columns:
  GROUP_:
    source_column: 'group'
    escape: true
  SALESYTD__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALESYTD AS text)), ''''), ''UTF8''), ''hex'')'
  SALESLASTYEAR__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(SALESLASTYEAR AS text)), ''''), ''UTF8''), ''hex'')'
  COSTYTD__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COSTYTD AS text)), ''''), ''UTF8''), ''hex'')'
  COSTLASTYEAR__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(COSTLASTYEAR AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SALESTERRITORY_HK: 'NAME'
  SALES_TERRITORY_FINANCIALS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'SALESYTD__CS'
      - 'SALESLASTYEAR__CS'
      - 'COSTYTD__CS'
      - 'COSTLASTYEAR__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
