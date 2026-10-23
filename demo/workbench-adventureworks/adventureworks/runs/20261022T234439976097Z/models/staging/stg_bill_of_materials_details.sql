-- Generated AutomateDV staging model for the raw-vault constructs on 'bill_of_materials_details'.
-- Computes the hash keys / hashdiffs the raw-vault models reference and passes
-- the source columns through (source binding: declared source schema).
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model:
  raw_5: 'BillOfMaterials'
derived_columns:
  ASSEMBLY_PRODUCTID: 'PRODUCTASSEMBLYID'
  COMPONENT_PRODUCTID: 'COMPONENTID'
null_columns:
  optional:
    - 'ASSEMBLY_PRODUCTID'
    - 'COMPONENT_PRODUCTID'
    - 'UNITMEASURECODE'
hashed_columns:
  LINK_BILL_OF_MATERIALS_HK:
    - 'ASSEMBLY_PRODUCTID'
    - 'COMPONENT_PRODUCTID'
    - 'UNITMEASURECODE'
  BILL_OF_MATERIALS_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'PERASSEMBLYQTY'
      - 'BOMLEVEL'
      - 'MODIFIEDDATE'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     null_columns=metadata_dict['null_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
