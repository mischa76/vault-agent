-- Generated AutomateDV staging model for the raw-vault constructs on 'product_assembly_component'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_4: 'BillOfMaterials'
derived_columns:
  ASSEMBLY_PRODUCTID: 'PRODUCTASSEMBLYID'
  COMPONENT_PRODUCTID: 'COMPONENTID'
  APPLIED_DTS: 'STARTDATE'
hashed_columns:
  ASSEMBLY_PRODUCT_HK: 'ASSEMBLY_PRODUCTID'
  COMPONENT_PRODUCT_HK: 'COMPONENT_PRODUCTID'
  UNITMEASURE_HK: 'UNITMEASURECODE'
  LINK_PRODUCT_ASSEMBLY_COMPONENT_HK:
    - 'ASSEMBLY_PRODUCTID'
    - 'COMPONENT_PRODUCTID'
    - 'UNITMEASURECODE'
  PRODUCT_ASSEMBLY_COMPONENT_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'BOMLEVEL'
      - 'PERASSEMBLYQTY'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
