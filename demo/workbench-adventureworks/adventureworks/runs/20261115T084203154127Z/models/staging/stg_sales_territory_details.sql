-- Generated AutomateDV staging model for the raw-vault constructs on 'sales_territory_details'.
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
  GROUP__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST("group" AS text)), ''''), ''UTF8''), ''hex'')'
  ROWGUID__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(ROWGUID AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
hashed_columns:
  SALESTERRITORY_HK: 'NAME'
  SALES_TERRITORY_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'GROUP__CS'
      - 'ROWGUID__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
