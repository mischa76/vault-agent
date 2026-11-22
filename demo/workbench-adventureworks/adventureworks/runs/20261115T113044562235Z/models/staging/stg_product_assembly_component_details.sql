-- Generated AutomateDV staging model for the raw-vault constructs on 'product_assembly_component_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'stg_product_assembly_component_details_via_product_and_product'
derived_columns:
  BOMLEVEL__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(BOMLEVEL AS text)), ''''), ''UTF8''), ''hex'')'
  PERASSEMBLYQTY__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(PERASSEMBLYQTY AS text)), ''''), ''UTF8''), ''hex'')'
  MODIFIEDDATE__CS: 'ENCODE(CONVERT_TO(NULLIF(TRIM(CAST(MODIFIEDDATE AS text)), ''''), ''UTF8''), ''hex'')'
null_columns:
  optional:
    - 'UNITMEASURECODE'
hashed_columns:
  LINK_PRODUCT_ASSEMBLY_COMPONENT_HK:
    - 'PRODUCTNUMBER'
    - 'COMPONENT_PRODUCTNUMBER'
    - 'UNITMEASURECODE'
  PRODUCT_ASSEMBLY_COMPONENT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'BOMLEVEL__CS'
      - 'PERASSEMBLYQTY__CS'
      - 'MODIFIEDDATE__CS'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
